from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from pathlib import PurePosixPath
from typing import Any, Callable

MAX_ARCHIVE_DEPTH = 2
MAX_ARCHIVE_FILE_COUNT = 200
MAX_ARCHIVE_ENTRY_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_MEMBER_NAME_LENGTH = 240


def is_safe_archive_member_name(name: str) -> bool:
    n = str(name or "").replace("\\", "/").strip()
    if not n:
        return False
    if len(n) > MAX_ARCHIVE_MEMBER_NAME_LENGTH:
        return False
    if any(ord(ch) < 32 for ch in n):
        return False
    p = PurePosixPath(n)
    if p.is_absolute():
        return False
    if any(part in ("..", "") for part in p.parts):
        return False
    return True


def detect_archive_kind(name: str) -> str | None:
    n = str(name or "").strip().lower()
    if n.endswith(".tar.gz") or n.endswith(".tgz"):
        return "tgz"
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(".tar"):
        return "tar"
    if n.endswith(".gz"):
        return "gz"
    if n.endswith(".rar"):
        return "rar"
    if n.endswith(".7z"):
        return "7z"
    return None


def sniff_archive_kind(data: bytes) -> str | None:
    b = bytes(data or b"")
    if len(b) >= 4 and b[:4] == b"PK\x03\x04":
        return "zip"
    if len(b) >= 2 and b[:2] == b"\x1f\x8b":
        return "gz"
    if len(b) >= 6 and b[:6] == b"Rar!\x1a\x07":
        return "rar"
    if len(b) >= 6 and b[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if len(b) >= 262 and b[257:262] == b"ustar":
        return "tar"
    return None


def process_archive(
    *,
    archive_name: str,
    archive_data: bytes,
    process_member: Callable[[str, bytes, int], list[dict[str, Any]]],
    depth: int = 0,
    limits: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    lim = limits or {}
    max_depth = int(lim.get("max_depth") or MAX_ARCHIVE_DEPTH)
    max_file_count = int(lim.get("max_file_count") or MAX_ARCHIVE_FILE_COUNT)
    max_entry_bytes = int(lim.get("max_entry_bytes") or MAX_ARCHIVE_ENTRY_BYTES)
    max_total_uncompressed_bytes = int(
        lim.get("max_total_uncompressed_bytes") or MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES
    )
    kind_from_sig = sniff_archive_kind(archive_data)
    kind_from_name = detect_archive_kind(archive_name)
    # For .tgz/.tar.gz, signature looks like gzip; keep richer name hint.
    if kind_from_name == "tgz" and kind_from_sig == "gz":
        kind = "tgz"
    else:
        kind = kind_from_sig or kind_from_name
    if kind is None:
        return []
    if depth > max_depth:
        return [{"type": "text", "name": "zip-error", "content": f"ZIP nesting too deep (>{max_depth})"}]
    out: list[dict[str, Any]] = []

    def _err(msg: str, *, error_code: str) -> list[dict[str, Any]]:
        base = {
            "type": "text",
            "name": ("zip-error" if kind == "zip" else "archive-error"),
            "error_code": str(error_code or "archive_error"),
            "content": (
                f"[ArchiveError]\n- error_code: {error_code}\n- format: {kind}\n- detail: {msg}"
            ),
        }
        return [base]

    try:
        if kind in {"rar", "7z"}:
            raise ValueError(
                f"unsupported archive format: {kind}; currently supported formats are zip/tar/tgz/gz"
            )
        if kind == "zip":
            with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
                infos = [x for x in zf.infolist() if not x.is_dir()]
                if len(infos) > max_file_count:
                    raise ValueError(f"ZIP has too many files ({len(infos)} > {max_file_count})")
                total_uncompressed = 0
                for info in infos:
                    if not is_safe_archive_member_name(info.filename):
                        raise ValueError(f"ZIP contains unsafe path: {info.filename}")
                    fsize = int(info.file_size or 0)
                    total_uncompressed += fsize
                    if fsize > max_entry_bytes:
                        raise ValueError(f"ZIP entry too large: {info.filename} ({fsize} > {max_entry_bytes})")
                    if total_uncompressed > max_total_uncompressed_bytes:
                        raise ValueError(
                            f"ZIP total uncompressed size too large ({total_uncompressed} > {max_total_uncompressed_bytes})"
                        )
                    with zf.open(info) as f:
                        out.extend(process_member(info.filename, f.read(), depth + 1))
            return out

        if kind in {"tar", "tgz"}:
            mode = "r:gz" if kind == "tgz" else "r:"
            with tarfile.open(fileobj=io.BytesIO(archive_data), mode=mode) as tf:
                all_members = list(tf.getmembers())
                for m in all_members:
                    if m.issym() or m.islnk():
                        raise ValueError(f"TAR contains link entry: {m.name}")
                    if m.ischr() or m.isblk() or m.isfifo():
                        raise ValueError(f"TAR contains device/fifo entry: {m.name}")
                members = [m for m in all_members if m.isfile()]
                if len(members) > max_file_count:
                    raise ValueError(f"TAR has too many files ({len(members)} > {max_file_count})")
                total_uncompressed = 0
                for m in members:
                    if not is_safe_archive_member_name(m.name):
                        raise ValueError(f"TAR contains unsafe path: {m.name}")
                    fsize = int(m.size or 0)
                    total_uncompressed += fsize
                    if fsize > max_entry_bytes:
                        raise ValueError(f"TAR entry too large: {m.name} ({fsize} > {max_entry_bytes})")
                    if total_uncompressed > max_total_uncompressed_bytes:
                        raise ValueError(
                            f"TAR total uncompressed size too large ({total_uncompressed} > {max_total_uncompressed_bytes})"
                        )
                    ext = tf.extractfile(m)
                    if ext is None:
                        continue
                    out.extend(process_member(m.name, ext.read(), depth + 1))
            return out

        if kind == "gz":
            raw = gzip.decompress(archive_data)
            if len(raw) > max_entry_bytes:
                raise ValueError(f"GZ entry too large ({len(raw)} > {max_entry_bytes})")
            name = str(archive_name or "file.gz")
            inner_name = name[:-3] if name.lower().endswith(".gz") else f"{name}.out"
            out.extend(process_member(inner_name, raw, depth + 1))
            return out
    except Exception as e:
        s = str(e).lower()
        code = "archive_parse_failed"
        if "unsupported archive format" in s:
            code = "archive_unsupported_format"
        elif "unsafe path" in s:
            code = "archive_path_traversal"
        elif "nesting too deep" in s:
            code = "archive_max_depth_exceeded"
        elif "too many files" in s:
            code = "archive_max_file_count_exceeded"
        elif "entry too large" in s:
            code = "archive_max_entry_bytes_exceeded"
        elif "total uncompressed size too large" in s:
            code = "archive_max_total_uncompressed_bytes_exceeded"
        elif "link entry" in s:
            code = "archive_link_entry_forbidden"
        elif "device/fifo entry" in s:
            code = "archive_special_entry_forbidden"
        return _err(str(e), error_code=code)
    return out


__all__ = [
    "MAX_ARCHIVE_DEPTH",
    "MAX_ARCHIVE_ENTRY_BYTES",
    "MAX_ARCHIVE_FILE_COUNT",
    "MAX_ARCHIVE_MEMBER_NAME_LENGTH",
    "MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES",
    "detect_archive_kind",
    "sniff_archive_kind",
    "is_safe_archive_member_name",
    "process_archive",
]

