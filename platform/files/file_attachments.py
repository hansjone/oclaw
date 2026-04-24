from __future__ import annotations

"""将上传文件解析为附件字典（不依赖 Streamlit）。"""

import io
import json
import os
import re
import zipfile
from functools import lru_cache
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

import pandas as pd
from docx import Document
from PIL import Image
from PyPDF2 import PdfReader

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.platform.files.tabular_attachment_store import save_dataframe, save_workbook


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


MAX_TEXT_CHARS = 12_000
EXCEL_PREVIEW_ROWS = 80
LARGE_TABLE_PREVIEW_ROWS = 20
MAX_ZIP_DEPTH = 2
MAX_ZIP_FILE_COUNT = 200
MAX_ZIP_ENTRY_BYTES = 10 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_TABULAR_ROWS_READ = 5000
DEFAULT_TABULAR_COLUMNS = 200
DEFAULT_TABULAR_CELL_CHARS = 500
DEFAULT_TABULAR_TOOL_MODE_ENABLED = True
DEFAULT_TABULAR_TOOL_MODE_MIN_ROWS = 20_000
DEFAULT_TABULAR_TOOL_MODE_MAX_BYTES = 30 * 1024 * 1024
DEFAULT_LARGE_TABLE_PREVIEW_ROWS = LARGE_TABLE_PREVIEW_ROWS
MAX_ZIP_MEMBER_NAME_LENGTH = 240
MAX_EXCEL_ZIP_FILE_COUNT = 500
MAX_EXCEL_ZIP_ENTRY_BYTES = 20 * 1024 * 1024
MAX_EXCEL_ZIP_TOTAL_UNCOMPRESSED_BYTES = 120 * 1024 * 1024
DEFAULT_MAX_EXCEL_SHEETS = 50


def _truncate_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    t = str(text or "")
    if len(t) <= limit:
        return t
    return t[:limit] + f"\n\n...[truncated to {limit} chars]"


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
    cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else (Path(PROJECT_ROOT) / "oclaw" / "oclaw.json").resolve()
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
    body = (
        f"# Table Summary\n"
        f"- rows: {rows}\n"
        f"- cols: {cols}\n"
        f"- sampled: {'yes' if sampled else 'no'}\n"
        f"- clipped_columns: {'yes' if clipped_columns else 'no'}\n"
        f"- clipped_cells: {'yes' if clipped_cells else 'no'}\n"
        f"- columns: {', '.join(header)}\n"
        f"- dtypes: {', '.join(dtypes)}\n\n"
        f"## Preview (first {min(rows, show_rows)} rows)\n"
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
    n = str(name or "").replace("\\", "/").strip()
    if not n:
        return False
    if len(n) > MAX_ZIP_MEMBER_NAME_LENGTH:
        return False
    if any(ord(ch) < 32 for ch in n):
        return False
    p = PurePosixPath(n)
    if p.is_absolute():
        return False
    if any(part in ("..", "") for part in p.parts):
        return False
    return True


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
    if _depth > MAX_ZIP_DEPTH:
        return [
            {
                "type": "text",
                "name": "zip-error",
                "content": f"ZIP nesting too deep (>{MAX_ZIP_DEPTH})",
            }
        ]
    attachments: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            infos = [x for x in zf.infolist() if not x.is_dir()]
            if len(infos) > MAX_ZIP_FILE_COUNT:
                raise ValueError(f"ZIP has too many files ({len(infos)} > {MAX_ZIP_FILE_COUNT})")
            total_uncompressed = 0
            for info in infos:
                if not _is_safe_zip_member_name(info.filename):
                    raise ValueError(f"ZIP contains unsafe path: {info.filename}")
                total_uncompressed += int(info.file_size or 0)
                if int(info.file_size or 0) > MAX_ZIP_ENTRY_BYTES:
                    raise ValueError(
                        f"ZIP entry too large: {info.filename} ({int(info.file_size or 0)} > {MAX_ZIP_ENTRY_BYTES})"
                    )
                if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                    raise ValueError(
                        "ZIP total uncompressed size too large "
                        f"({total_uncompressed} > {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES})"
                    )
                with zf.open(info) as f:
                    data = f.read()
                    att = process_file_data(info.filename, data, _zip_depth=_depth + 1)
                    if att:
                        attachments.extend(att)
    except Exception as e:
        attachments.append(
            {
                "type": "text",
                "name": "zip-error",
                "content": f"Error parsing zip: {e}",
            }
        )
    return attachments


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
            attachments.append({"type": "text", "name": name, "content": _truncate_text(text)})
        except Exception as e:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing docx: {e}")})

    elif ext == "pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            attachments.append({"type": "text", "name": name, "content": _pdf_summary_text(reader)})
        except Exception as e:
            attachments.append({"type": "text", "name": name, "content": _truncate_text(f"Error parsing pdf: {e}")})

    elif ext in ("txt", "py", "js", "html", "css", "md", "json", "yaml", "yml", "sh", "log"):
        text = _decode_text_bytes(data)
        if ext == "html":
            text = _clean_html_to_text(text)
        attachments.append({"type": "text", "name": name, "content": _truncate_text(text)})

    elif ext == "zip":
        attachments.extend(process_zip(data, _depth=_zip_depth))

    return attachments


__all__ = ["process_zip", "process_file_data", "clear_attachment_limits_cache"]
