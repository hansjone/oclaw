from __future__ import annotations

"""将上传文件解析为附件字典（不依赖 Streamlit）。"""

import io
import json
import os
import re
import subprocess
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document
from PIL import Image
from PyPDF2 import PdfReader

from svc.config.paths import PROJECT_ROOT
from svc.files.archive_processor import (
    MAX_ARCHIVE_DEPTH,
    MAX_ARCHIVE_ENTRY_BYTES,
    MAX_ARCHIVE_FILE_COUNT,
    MAX_ARCHIVE_MEMBER_NAME_LENGTH,
    MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES,
    detect_archive_kind,
    is_safe_archive_member_name,
    process_archive,
)
from svc.files.attachment_assets import AttachmentAssetStore
from svc.files.tabular_attachment_store import save_dataframe, save_workbook
from svc.files.text_attachment_store import (
    DEFAULT_TEXT_CHUNK_OVERLAP,
    DEFAULT_TEXT_CHUNK_SIZE,
    DEFAULT_TEXT_INLINE_MAX_CHARS,
    save_text_document,
)


def _sniff_image_mime(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _ffprobe_exists() -> bool:
    try:
        p = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
        return p.returncode == 0
    except Exception:
        return False


def _extract_video_meta_from_ffprobe(obj: dict[str, Any]) -> dict[str, Any]:
    fmt = obj.get("format") if isinstance(obj.get("format"), dict) else {}
    streams = obj.get("streams") if isinstance(obj.get("streams"), list) else []
    duration_sec = None
    if isinstance(fmt, dict) and fmt.get("duration") is not None:
        try:
            duration_sec = float(fmt.get("duration"))
        except Exception:
            duration_sec = None
    width = None
    height = None
    fps = None
    for s in streams:
        if not isinstance(s, dict):
            continue
        if str(s.get("codec_type") or "") != "video":
            continue
        if s.get("width") is not None and s.get("height") is not None:
            try:
                width = int(s.get("width") or 0) or None
                height = int(s.get("height") or 0) or None
            except Exception:
                width = width
                height = height
        fr = str(s.get("avg_frame_rate") or s.get("r_frame_rate") or "").strip()
        if fr and fr != "0/0" and "/" in fr:
            try:
                a, b = fr.split("/", 1)
                fa = float(a)
                fb = float(b)
                if fb:
                    fps = fa / fb
            except Exception:
                fps = fps
        break
    out: dict[str, Any] = {}
    if duration_sec is not None:
        out["duration_sec"] = duration_sec
    if width is not None:
        out["width"] = width
    if height is not None:
        out["height"] = height
    if fps is not None:
        out["fps"] = fps
    return out


def _ffprobe_video_meta(path: Path) -> dict[str, Any]:
    if not _ffprobe_exists():
        return {}
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
        if p.returncode != 0:
            return {}
        obj = json.loads(p.stdout or "{}")
        if not isinstance(obj, dict):
            return {}
        return _extract_video_meta_from_ffprobe(obj)
    except Exception:
        return {}


MAX_TEXT_CHARS = 12_000
EXCEL_PREVIEW_ROWS = 80
LARGE_TABLE_PREVIEW_ROWS = 20
MAX_ZIP_DEPTH = MAX_ARCHIVE_DEPTH
MAX_ZIP_FILE_COUNT = MAX_ARCHIVE_FILE_COUNT
MAX_ZIP_ENTRY_BYTES = MAX_ARCHIVE_ENTRY_BYTES
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES
DEFAULT_TABULAR_ROWS_READ = 5000
DEFAULT_TABULAR_COLUMNS = 200
DEFAULT_TABULAR_CELL_CHARS = 500
DEFAULT_TABULAR_TOOL_MODE_ENABLED = True
DEFAULT_TABULAR_TOOL_MODE_MIN_ROWS = 5_000
DEFAULT_TABULAR_TOOL_MODE_MAX_BYTES = 30 * 1024 * 1024
DEFAULT_LARGE_TABLE_PREVIEW_ROWS = LARGE_TABLE_PREVIEW_ROWS
MAX_ZIP_MEMBER_NAME_LENGTH = MAX_ARCHIVE_MEMBER_NAME_LENGTH
MAX_EXCEL_ZIP_FILE_COUNT = 500
MAX_EXCEL_ZIP_ENTRY_BYTES = 20 * 1024 * 1024
MAX_EXCEL_ZIP_TOTAL_UNCOMPRESSED_BYTES = 120 * 1024 * 1024
DEFAULT_MAX_EXCEL_SHEETS = 50
DEFAULT_TEXT_QUERY_TOP_K = 5


def _truncate_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    t = str(text or "")
    if len(t) <= limit:
        return t
    return t[:limit] + f"\n\n...[truncated to {limit} chars]"


def _text_ref_summary(*, name: str, chars: int, chunks: int, source_kind: str, preview: str, top_k: int) -> str:
    return _truncate_text(
        (
            f"# Text Document Summary\n"
            f"- name: {name}\n"
            f"- source_kind: {source_kind}\n"
            f"- chars: {chars}\n"
            f"- chunks: {chunks}\n"
            f"- mode: text_ref\n"
            f"- query_tool: query_text_attachment\n"
            f"- note: use `text_id` from accompanying `text_ref` attachment; recommended top_k <= {top_k}\n\n"
            f"## Preview (first {min(len(preview), 1500)} chars)\n"
            f"{preview[:1500]}"
        ),
        limit=MAX_TEXT_CHARS,
    )


def _decode_text_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gbk")
        except Exception:
            return "Error decoding text file (unknown encoding)"


def _clean_html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", str(raw or ""))
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _safe_int(raw: Any, default: int, *, min_value: int = 1, max_value: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < min_value:
        return default
    return min(value, max_value)


@lru_cache(maxsize=1)
def _attachments_limits() -> dict[str, Any]:
    cfg_path_raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
    cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else (Path(PROJECT_ROOT) / "oclaw.json").resolve()
    if not cfg_path.is_absolute():
        cfg_path = (Path(PROJECT_ROOT) / cfg_path).resolve()
    tabular_cfg: dict[str, Any] = {}
    try:
        obj = json.loads(cfg_path.read_text(encoding="utf-8"))
        tabular_cfg = (
            (((obj or {}).get("plugins") or {}).get("entries") or {}).get("memory-wiki", {}).get("auto", {}).get("attachments", {}).get("tabular", {}) or {}
        )
    except Exception:
        tabular_cfg = {}
    return {
        "rows_read": _safe_int(tabular_cfg.get("max_rows_read"), DEFAULT_TABULAR_ROWS_READ),
        "columns": _safe_int(tabular_cfg.get("max_columns"), DEFAULT_TABULAR_COLUMNS),
        "cell_chars": _safe_int(tabular_cfg.get("max_cell_chars"), DEFAULT_TABULAR_CELL_CHARS),
        "max_excel_sheets": _safe_int(tabular_cfg.get("max_excel_sheets"), DEFAULT_MAX_EXCEL_SHEETS, max_value=500),
        "large_table_preview_rows": _safe_int(
            tabular_cfg.get("large_table_preview_rows"), DEFAULT_LARGE_TABLE_PREVIEW_ROWS, max_value=500
        ),
        "tool_mode_enabled": bool(tabular_cfg.get("tool_mode_enabled", DEFAULT_TABULAR_TOOL_MODE_ENABLED)),
        "tool_mode_min_rows": _safe_int(tabular_cfg.get("tool_mode_min_rows"), DEFAULT_TABULAR_TOOL_MODE_MIN_ROWS),
        "tool_mode_max_bytes": _safe_int(
            tabular_cfg.get("tool_mode_max_bytes"), DEFAULT_TABULAR_TOOL_MODE_MAX_BYTES, max_value=500 * 1024 * 1024
        ),
        "text_inline_max_chars": _safe_int(
            tabular_cfg.get("text_inline_max_chars"), DEFAULT_TEXT_INLINE_MAX_CHARS, max_value=200_000
        ),
        "text_chunk_size": _safe_int(tabular_cfg.get("text_chunk_size"), DEFAULT_TEXT_CHUNK_SIZE, max_value=8_000),
        "text_chunk_overlap": _safe_int(
            tabular_cfg.get("text_chunk_overlap"), DEFAULT_TEXT_CHUNK_OVERLAP, max_value=4_000
        ),
        "text_query_top_k": _safe_int(tabular_cfg.get("text_query_top_k"), DEFAULT_TEXT_QUERY_TOP_K, max_value=50),
        "archive_max_depth": _safe_int(tabular_cfg.get("archive_max_depth"), MAX_ARCHIVE_DEPTH, max_value=10),
        "archive_max_file_count": _safe_int(
            tabular_cfg.get("archive_max_file_count"), MAX_ARCHIVE_FILE_COUNT, max_value=20_000
        ),
        "archive_max_entry_bytes": _safe_int(
            tabular_cfg.get("archive_max_entry_bytes"), MAX_ARCHIVE_ENTRY_BYTES, max_value=2_000_000_000
        ),
        "archive_max_total_uncompressed_bytes": _safe_int(
            tabular_cfg.get("archive_max_total_uncompressed_bytes"),
            MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES,
            max_value=5_000_000_000,
        ),
    }


def clear_attachment_limits_cache() -> None:
    _attachments_limits.cache_clear()


def _clip_tabular_cells(df: pd.DataFrame, *, max_cell_chars: int) -> tuple[pd.DataFrame, bool]:
    clipped_any = False

    def _clip_cell(value: Any) -> Any:
        nonlocal clipped_any
        if value is None:
            return value
        s = str(value)
        if len(s) <= max_cell_chars:
            return value
        clipped_any = True
        return s[:max_cell_chars] + "...[cell-truncated]"

    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(_clip_cell)
    return out, clipped_any


def _dataframe_summary_text(
    df: pd.DataFrame,
    *,
    sampled: bool = False,
    clipped_columns: bool = False,
    clipped_cells: bool = False,
    preview_rows: int = EXCEL_PREVIEW_ROWS,
) -> str:
    rows = int(len(df.index))
    cols = int(len(df.columns))
    header = [str(x) for x in list(df.columns)]
    dtypes = [f"{str(k)}:{str(v)}" for k, v in df.dtypes.items()]
    show_rows = max(1, int(preview_rows or EXCEL_PREVIEW_ROWS))
    sample = df.head(show_rows).to_string(index=False)
    rows_scope_line = (
        f"## Preview (first {min(rows, show_rows)} rows)"
        if rows > show_rows
        else f"## Full table included ({rows} rows)"
    )
    body = (
        f"# Table Summary\n"
        f"- rows: {rows}\n"
        f"- cols: {cols}\n"
        f"- sampled: {'yes' if sampled else 'no'}\n"
        f"- clipped_columns: {'yes' if clipped_columns else 'no'}\n"
        f"- clipped_cells: {'yes' if clipped_cells else 'no'}\n"
        f"- columns: {', '.join(header)}\n"
        f"- dtypes: {', '.join(dtypes)}\n\n"
        f"{rows_scope_line}\n"
        f"{sample}"
    )
    return _truncate_text(body)


def _pdf_summary_text(reader: PdfReader) -> str:
    pages = list(getattr(reader, "pages", []) or [])
    chunks: list[str] = [f"# PDF Summary\n- pages: {len(pages)}\n"]
    for idx, page in enumerate(pages, start=1):
        txt = ""
        try:
            txt = str(page.extract_text() or "").strip()
        except Exception:
            txt = ""
        if not txt:
            txt = "(empty page text)"
        chunks.append(f"## Page {idx}\n{txt}")
    return _truncate_text("\n\n".join(chunks))


def _is_safe_zip_member_name(name: str) -> bool:
    return is_safe_archive_member_name(name)


def _validate_excel_zip_payload(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = [x for x in zf.infolist() if not x.is_dir()]
            if len(infos) > MAX_EXCEL_ZIP_FILE_COUNT:
                return f"excel zip has too many entries ({len(infos)} > {MAX_EXCEL_ZIP_FILE_COUNT})"
            total_uncompressed = 0
            for info in infos:
                if not _is_safe_zip_member_name(info.filename):
                    return f"excel zip contains unsafe path: {info.filename}"
                fsize = int(info.file_size or 0)
                total_uncompressed += fsize
                if fsize > MAX_EXCEL_ZIP_ENTRY_BYTES:
                    return f"excel zip entry too large: {info.filename} ({fsize} > {MAX_EXCEL_ZIP_ENTRY_BYTES})"
                if total_uncompressed > MAX_EXCEL_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                    return (
                        "excel zip total uncompressed size too large "
                        f"({total_uncompressed} > {MAX_EXCEL_ZIP_TOTAL_UNCOMPRESSED_BYTES})"
                    )
        return None
    except Exception:
        return "invalid excel zip payload"


def process_zip(zip_data: bytes, *, _depth: int = 0) -> list[dict[str, Any]]:
    limits = _attachments_limits()
    return process_archive(
        archive_name="bundle.zip",
        archive_data=zip_data,
        process_member=lambda n, b, d: process_file_data(n, b, _zip_depth=d),
        depth=_depth,
        limits={
            "max_depth": int(limits.get("archive_max_depth") or MAX_ARCHIVE_DEPTH),
            "max_file_count": int(limits.get("archive_max_file_count") or MAX_ARCHIVE_FILE_COUNT),
            "max_entry_bytes": int(limits.get("archive_max_entry_bytes") or MAX_ARCHIVE_ENTRY_BYTES),
            "max_total_uncompressed_bytes": int(
                limits.get("archive_max_total_uncompressed_bytes") or MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES
            ),
        },
    )


def expand_attachment_ref(
    att: dict[str, Any],
    *,
    data: bytes | None = None,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Expand ``binary_ref`` (or raw bytes) into parsed attachment dicts for the agent."""
    if not isinstance(att, dict):
        return []
    t = str(att.get("type") or "").strip().lower()
    if t and t not in {"binary_ref"}:
        return [att]
    aid = str(att.get("attachment_id") or att.get("attachmentId") or "").strip().lower()
    meta = None
    if data is None and aid:
        blob, meta = AttachmentAssetStore().load_bytes(aid)
        if not blob:
            return [att] if t == "binary_ref" else []
        data = blob
        name = name or str(getattr(meta, "name", "") or "file")
    if data is None:
        return [att] if t == "binary_ref" else []
    fname = str(name or att.get("name") or getattr(meta, "name", "") or "file")
    got = process_file_data(fname, data)
    if got:
        return got
    if aid:
        if meta is None:
            meta = AttachmentAssetStore().get_meta(aid)
        return [
            {
                "type": "binary_ref",
                "attachment_id": aid,
                "name": fname,
                "mime": str(att.get("mime") or getattr(meta, "mime", "") or "application/octet-stream"),
                "bytes": att.get("bytes") if att.get("bytes") is not None else getattr(meta, "bytes", None),
            }
        ]
    return []


def process_file_data(name: str, data: bytes, *, _zip_depth: int = 0) -> list[dict[str, Any]]:
    ext = name.split(".")[-1].lower() if "." in name else ""
    attachments: list[dict[str, Any]] = []

    if ext in ("png", "jpg", "jpeg", "webp", "gif", "jfif", "pjpeg", "bmp", "tif", "tiff"):
        if ext == "png":
            mime = "image/png"
        elif ext in ("jpg", "jpeg", "jfif", "pjpeg"):
            mime = "image/jpeg"
        elif ext == "webp":
            mime = "image/webp"
        elif ext == "gif":
            mime = "image/gif"
        elif ext == "bmp":
            mime = "image/bmp"
        elif ext in ("tif", "tiff"):
            mime = "image/tiff"
        width = None
        height = None
        try:
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except Exception:
            pass
        meta = AttachmentAssetStore().save_bytes(data, filename=name, mime=mime, width=width, height=height)
        attachments.append(
            {
                "type": "image_ref",
                "name": meta.name,
                "mime": meta.mime,
                "attachment_id": meta.attachment_id,
                "bytes": meta.bytes,
                "width": meta.width,
                "height": meta.height,
            }
        )
        return attachments

    sniff_mime = _sniff_image_mime(data)
    if sniff_mime:
        width = None
        height = None
        try:
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except Exception:
            pass
        meta = AttachmentAssetStore().save_bytes(data, filename=name, mime=sniff_mime, width=width, height=height)
        attachments.append(
            {
                "type": "image_ref",
                "name": meta.name,
                "mime": meta.mime,
                "attachment_id": meta.attachment_id,
                "bytes": meta.bytes,
                "width": meta.width,
                "height": meta.height,
            }
        )
        return attachments

    if ext in ("mp4", "mov", "mkv", "webm", "avi", "m4v"):
        mime = "video/mp4"
        if ext == "webm":
            mime = "video/webm"
        elif ext == "mov":
            mime = "video/quicktime"
        elif ext == "mkv":
            mime = "video/x-matroska"
        elif ext == "avi":
            mime = "video/x-msvideo"
        meta = AttachmentAssetStore().save_bytes(data, filename=name, mime=mime)
        probe_meta: dict[str, Any] = {}
        try:
            p = AttachmentAssetStore().get_local_path(str(meta.attachment_id))
            if p is not None:
                probe_meta = _ffprobe_video_meta(p)
        except Exception:
            probe_meta = {}
        attachments.append(
            {
                "type": "video_ref",
                "name": meta.name,
                "mime": meta.mime,
                "attachment_id": meta.attachment_id,
                "bytes": meta.bytes,
                **probe_meta,
            }
        )
        attachments.append(
            {
                "type": "text",
                "name": name,
                "content": _truncate_text(
                    "".join(
                        [
                            "# Video Attachment\n",
                            f"- name: {meta.name}\n",
                            f"- mime: {meta.mime}\n",
                            f"- bytes: {meta.bytes}\n",
                            (
                                f"- duration_sec: {probe_meta.get('duration_sec')}\n"
                                if probe_meta.get("duration_sec") is not None
                                else ""
                            ),
                            (
                                f"- size: {probe_meta.get('width')}x{probe_meta.get('height')}\n"
                                if probe_meta.get("width") and probe_meta.get("height")
                                else ""
                            ),
                            (f"- fps: {probe_meta.get('fps')}\n" if probe_meta.get("fps") is not None else ""),
                            "- mode: video_ref\n",
                            "- query_tool: query_video_attachment\n",
                            "- note: use `attachment_id` from accompanying `video_ref` attachment.\n",
                        ]
                    ),
                    limit=MAX_TEXT_CHARS,
                ),
            }
        )
        return attachments

    if ext in ("xlsx", "xls", "csv"):
        try:
            if ext == "xlsx":
                zip_err = _validate_excel_zip_payload(data)
                if zip_err:
                    attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing excel/csv: {zip_err}")})
                    return attachments
            limits = _attachments_limits()
            rows_read = int(limits.get("rows_read") or DEFAULT_TABULAR_ROWS_READ)
            max_columns = int(limits.get("columns") or DEFAULT_TABULAR_COLUMNS)
            max_cell_chars = int(limits.get("cell_chars") or DEFAULT_TABULAR_CELL_CHARS)
            max_excel_sheets = int(limits.get("max_excel_sheets") or DEFAULT_MAX_EXCEL_SHEETS)
            large_table_preview_rows = int(
                limits.get("large_table_preview_rows") or DEFAULT_LARGE_TABLE_PREVIEW_ROWS
            )
            tool_mode_enabled = bool(limits.get("tool_mode_enabled", DEFAULT_TABULAR_TOOL_MODE_ENABLED))
            tool_mode_min_rows = int(limits.get("tool_mode_min_rows") or DEFAULT_TABULAR_TOOL_MODE_MIN_ROWS)
            tool_mode_max_bytes = int(limits.get("tool_mode_max_bytes") or DEFAULT_TABULAR_TOOL_MODE_MAX_BYTES)
            if ext == "csv":
                df = pd.read_csv(io.BytesIO(data), nrows=rows_read)
            else:
                df = pd.read_excel(io.BytesIO(data), nrows=rows_read)
            sampled = int(len(df.index)) >= rows_read
            estimated_rows = 0
            if ext == "csv":
                estimated_rows = max(0, int(data.count(b"\n")) - 1)
            else:
                estimated_rows = int(len(df.index))
            clipped_columns = int(len(df.columns)) > max_columns
            if clipped_columns:
                df = df.iloc[:, :max_columns]
            df, clipped_cells = _clip_tabular_cells(df, max_cell_chars=max_cell_chars)
            tool_mode = bool(
                tool_mode_enabled
                and int(len(data or b"")) <= tool_mode_max_bytes
                and (estimated_rows >= tool_mode_min_rows or (ext in ("xlsx", "xls") and sampled))
            )
            attachments.append(
                {
                    "type": "text",
                    "name": name,
                    "content": _dataframe_summary_text(
                        df,
                        sampled=sampled,
                        clipped_columns=clipped_columns,
                        clipped_cells=clipped_cells,
                        preview_rows=(large_table_preview_rows if tool_mode else EXCEL_PREVIEW_ROWS),
                    )
                    + (
                        (
                            f"\n\n# Large Table Mode\n- estimated_rows: {estimated_rows}\n- query_tool: query_tabular_attachment\n"
                            "- note: use the `table_id` from the accompanying `tabular_ref` attachment to query full data."
                        )
                        if tool_mode
                        else ""
                    ),
                }
            )
            if tool_mode:
                workbook_sheets: dict[str, pd.DataFrame]
                clipped_sheets = False
                if ext == "csv":
                    full_df = pd.read_csv(io.BytesIO(data), dtype=str)
                    if int(len(full_df.columns)) > max_columns:
                        full_df = full_df.iloc[:, :max_columns]
                    full_df, _ = _clip_tabular_cells(full_df, max_cell_chars=max_cell_chars)
                    workbook_sheets = {"Sheet1": full_df}
                else:
                    excel_obj = pd.read_excel(io.BytesIO(data), dtype=str, sheet_name=None)
                    workbook_sheets = {}
                    sheet_items = list((excel_obj or {}).items())
                    if len(sheet_items) > max_excel_sheets:
                        clipped_sheets = True
                        sheet_items = sheet_items[:max_excel_sheets]
                    for sheet_name, sheet_df in sheet_items:
                        sdf = sheet_df
                        if int(len(sdf.columns)) > max_columns:
                            sdf = sdf.iloc[:, :max_columns]
                        sdf, _ = _clip_tabular_cells(sdf, max_cell_chars=max_cell_chars)
                        workbook_sheets[str(sheet_name or f"Sheet{len(workbook_sheets)+1}")] = sdf
                mime = "text/csv" if ext == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                meta = AttachmentAssetStore().save_bytes(data, filename=name, mime=mime)
                table_meta = (
                    save_dataframe(attachment_id=str(meta.attachment_id), name=name, df=workbook_sheets.get("Sheet1", pd.DataFrame()))
                    if ext == "csv"
                    else save_workbook(attachment_id=str(meta.attachment_id), name=name, sheets=workbook_sheets)
                )
                attachments.append(
                    {
                        "type": "tabular_ref",
                        "name": str(name),
                        "attachment_id": str(meta.attachment_id),
                        "table_id": str(table_meta.get("table_id") or ""),
                        "rows": int(table_meta.get("rows") or 0),
                        "cols": int(table_meta.get("cols") or 0),
                        "columns": list(table_meta.get("columns") or []),
                        "sheets": list(table_meta.get("sheets") or []),
                    }
                )
                if clipped_sheets:
                    attachments.append(
                        {
                            "type": "text",
                            "name": f"{name}.sheet-limit",
                            "content": (
                                f"Excel workbook contains too many sheets; only the first {max_excel_sheets} sheets were stored "
                                "for tool-mode querying. Adjust max_excel_sheets if full coverage is required."
                            ),
                        }
                    )
        except Exception as e:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing excel/csv: {e}")})

    elif ext == "docx":
        try:
            doc = Document(io.BytesIO(data))
            text = "\n".join([p.text for p in doc.paragraphs])
            limits = _attachments_limits()
            inline_cap = int(limits.get("text_inline_max_chars") or DEFAULT_TEXT_INLINE_MAX_CHARS)
            if len(str(text or "")) <= inline_cap:
                attachments.append({"type": "text", "name": name, "content": _truncate_text(text, limit=inline_cap)})
            else:
                meta = AttachmentAssetStore().save_bytes(
                    data,
                    filename=name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                text_meta = save_text_document(
                    attachment_id=str(meta.attachment_id),
                    name=name,
                    text=str(text or ""),
                    source_kind="docx",
                    chunk_size=int(limits.get("text_chunk_size") or DEFAULT_TEXT_CHUNK_SIZE),
                    chunk_overlap=int(limits.get("text_chunk_overlap") or DEFAULT_TEXT_CHUNK_OVERLAP),
                )
                top_k = int(limits.get("text_query_top_k") or DEFAULT_TEXT_QUERY_TOP_K)
                attachments.append(
                    {
                        "type": "text",
                        "name": name,
                        "content": _text_ref_summary(
                            name=name,
                            chars=int(text_meta.get("chars") or 0),
                            chunks=int(text_meta.get("chunks") or 0),
                            source_kind="docx",
                            preview=str(text or ""),
                            top_k=top_k,
                        ),
                    }
                )
                attachments.append(
                    {
                        "type": "text_ref",
                        "name": str(name),
                        "attachment_id": str(meta.attachment_id),
                        "text_id": str(text_meta.get("text_id") or ""),
                        "chars": int(text_meta.get("chars") or 0),
                        "chunks": int(text_meta.get("chunks") or 0),
                        "source_kind": "docx",
                    }
                )
        except Exception as e:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing docx: {e}")})

    elif ext == "pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            text = _pdf_summary_text(reader)
            limits = _attachments_limits()
            inline_cap = int(limits.get("text_inline_max_chars") or DEFAULT_TEXT_INLINE_MAX_CHARS)
            if len(str(text or "")) <= inline_cap:
                attachments.append({"type": "text", "name": name, "content": _truncate_text(text, limit=inline_cap)})
            else:
                meta = AttachmentAssetStore().save_bytes(data, filename=name, mime="application/pdf")
                text_meta = save_text_document(
                    attachment_id=str(meta.attachment_id),
                    name=name,
                    text=str(text or ""),
                    source_kind="pdf",
                    chunk_size=int(limits.get("text_chunk_size") or DEFAULT_TEXT_CHUNK_SIZE),
                    chunk_overlap=int(limits.get("text_chunk_overlap") or DEFAULT_TEXT_CHUNK_OVERLAP),
                )
                top_k = int(limits.get("text_query_top_k") or DEFAULT_TEXT_QUERY_TOP_K)
                attachments.append(
                    {
                        "type": "text",
                        "name": name,
                        "content": _text_ref_summary(
                            name=name,
                            chars=int(text_meta.get("chars") or 0),
                            chunks=int(text_meta.get("chunks") or 0),
                            source_kind="pdf",
                            preview=str(text or ""),
                            top_k=top_k,
                        ),
                    }
                )
                attachments.append(
                    {
                        "type": "text_ref",
                        "name": str(name),
                        "attachment_id": str(meta.attachment_id),
                        "text_id": str(text_meta.get("text_id") or ""),
                        "chars": int(text_meta.get("chars") or 0),
                        "chunks": int(text_meta.get("chunks") or 0),
                        "source_kind": "pdf",
                    }
                )
        except Exception as e:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing pdf: {e}")})

    elif ext in ("txt", "py", "js", "html", "css", "md", "json", "yaml", "yml", "sh", "log"):
        text = _decode_text_bytes(data)
        if ext == "html":
            text = _clean_html_to_text(text)
        limits = _attachments_limits()
        inline_cap = int(limits.get("text_inline_max_chars") or DEFAULT_TEXT_INLINE_MAX_CHARS)
        if len(str(text or "")) <= inline_cap:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(text, limit=inline_cap)})
        else:
            meta = AttachmentAssetStore().save_bytes(data, filename=name, mime="text/plain")
            text_meta = save_text_document(
                attachment_id=str(meta.attachment_id),
                name=name,
                text=str(text or ""),
                source_kind=ext or "text",
                chunk_size=int(limits.get("text_chunk_size") or DEFAULT_TEXT_CHUNK_SIZE),
                chunk_overlap=int(limits.get("text_chunk_overlap") or DEFAULT_TEXT_CHUNK_OVERLAP),
            )
            top_k = int(limits.get("text_query_top_k") or DEFAULT_TEXT_QUERY_TOP_K)
            attachments.append(
                {
                    "type": "text",
                    "name": name,
                    "content": _text_ref_summary(
                        name=name,
                        chars=int(text_meta.get("chars") or 0),
                        chunks=int(text_meta.get("chunks") or 0),
                        source_kind=str(text_meta.get("source_kind") or ext or "text"),
                        preview=str(text or ""),
                        top_k=top_k,
                    ),
                }
            )
            attachments.append(
                {
                    "type": "text_ref",
                    "name": str(name),
                    "attachment_id": str(meta.attachment_id),
                    "text_id": str(text_meta.get("text_id") or ""),
                    "chars": int(text_meta.get("chars") or 0),
                    "chunks": int(text_meta.get("chunks") or 0),
                    "source_kind": str(text_meta.get("source_kind") or ext or "text"),
                }
            )

    elif detect_archive_kind(name):
        limits = _attachments_limits()
        attachments.extend(
            process_archive(
                archive_name=name,
                archive_data=data,
                process_member=lambda n, b, d: process_file_data(n, b, _zip_depth=d),
                depth=_zip_depth,
                limits={
                    "max_depth": int(limits.get("archive_max_depth") or MAX_ARCHIVE_DEPTH),
                    "max_file_count": int(limits.get("archive_max_file_count") or MAX_ARCHIVE_FILE_COUNT),
                    "max_entry_bytes": int(limits.get("archive_max_entry_bytes") or MAX_ARCHIVE_ENTRY_BYTES),
                    "max_total_uncompressed_bytes": int(
                        limits.get("archive_max_total_uncompressed_bytes") or MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES
                    ),
                },
            )
        )

    return attachments


__all__ = ["process_zip", "process_file_data", "expand_attachment_ref", "clear_attachment_limits_cache"]
