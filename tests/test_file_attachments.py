from __future__ import annotations

import io
import json
import gzip
import tarfile
import zipfile
from pathlib import Path

import pandas as pd
import svc.files.file_attachments as fa
from svc.files.file_attachments import process_file_data
from svc.files.tabular_attachment_store import (
    aggregate_table,
    analyze_table_full_scan,
    query_table,
    run_table_sql,
    save_workbook,
)
from svc.files.text_attachment_store import query_text_document


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _tar_bytes(files: dict[str, bytes], *, gz: bool = False) -> bytes:
    buf = io.BytesIO()
    mode = "w:gz" if gz else "w"
    with tarfile.open(fileobj=buf, mode=mode) as tf:
        for name, data in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_csv_is_summarized_not_full_dump() -> None:
    payload = (
        "c1,c2,c3\n"
        "1,2,3\n"
        "4,5,6\n"
    ).encode("utf-8")
    out = process_file_data("table.csv", payload)
    assert out and out[0]["type"] == "text"
    content = str(out[0].get("content") or "")
    assert "# Table Summary" in content
    assert "rows: 2" in content
    assert "cols: 3" in content
    assert "## Full table included (2 rows)" in content


def test_long_txt_emits_text_ref_and_can_query() -> None:
    payload = ("A" * 15000 + "\nneedle\n" + "B" * 2000).encode("utf-8")
    out = process_file_data("notes.txt", payload)
    text_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "text_ref"]
    assert text_refs
    text_id = str(text_refs[0].get("text_id") or "")
    assert text_id
    got = query_text_document(text_id=text_id, query="needle", top_k=3, offset=0)
    assert bool(got.get("ok"))
    rows = got.get("rows") or []
    assert rows
    assert any("needle" in str(x.get("content") or "") for x in rows)


def test_video_upload_emits_video_ref() -> None:
    # Minimal MP4 header-like bytes; parser should not crash and should still store as video_ref.
    payload = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    out = process_file_data("clip.mp4", payload)
    vrefs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "video_ref"]
    assert vrefs
    vr = vrefs[0]
    assert str(vr.get("attachment_id") or "")
    assert str(vr.get("mime") or "").startswith("video/")


def test_zip_file_count_limit_returns_error_attachment() -> None:
    files = {f"f{i}.txt": b"x" for i in range(205)}
    out = process_file_data("bulk.zip", _zip_bytes(files))
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "zip-error"
    assert "too many files" in str(first.get("content") or "").lower()


def test_tar_path_traversal_is_blocked() -> None:
    payload = _tar_bytes({"../evil.txt": b"x"})
    out = process_file_data("unsafe.tar", payload)
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "archive-error"
    assert "unsafe path" in str(first.get("content") or "").lower()


def test_tgz_is_parsed_and_members_processed() -> None:
    payload = _tar_bytes({"ok.txt": b"hello"}, gz=True)
    out = process_file_data("bundle.tgz", payload)
    assert out
    assert any(str(x.get("type") or "") == "text" and "hello" in str(x.get("content") or "") for x in out)


def test_tar_link_entry_is_explicitly_rejected() -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        ti = tarfile.TarInfo(name="target.txt")
        data = b"ok"
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
        lnk = tarfile.TarInfo(name="sym")
        lnk.type = tarfile.SYMTYPE
        lnk.linkname = "target.txt"
        tf.addfile(lnk)
    out = process_file_data("has-link.tar", buf.getvalue())
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "archive-error"
    assert str(first.get("error_code") or "") == "archive_link_entry_forbidden"


def test_gz_single_file_is_decompressed_and_processed() -> None:
    payload = gzip.compress(b"hello-gz")
    out = process_file_data("note.txt.gz", payload)
    assert out
    assert any(str(x.get("type") or "") == "text" and "hello-gz" in str(x.get("content") or "") for x in out)


def test_rar_returns_explicit_unsupported_error() -> None:
    out = process_file_data("bundle.rar", b"not-a-real-rar")
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "archive-error"
    assert "unsupported archive format" in str(first.get("content") or "").lower()


def test_7z_returns_explicit_unsupported_error() -> None:
    out = process_file_data("bundle.7z", b"not-a-real-7z")
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "archive-error"
    assert "unsupported archive format" in str(first.get("content") or "").lower()
    assert str(first.get("error_code") or "") == "archive_unsupported_format"


def test_archive_signature_detection_overrides_misleading_extension() -> None:
    payload = _zip_bytes({"ok.txt": b"sig-ok"})
    out = process_file_data("misleading.tar", payload)
    assert out
    assert any(str(x.get("type") or "") == "text" and "sig-ok" in str(x.get("content") or "") for x in out)


def test_archive_limits_can_be_overridden_by_config(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "archive_max_depth": 1,
                                "archive_max_file_count": 2,
                                "archive_max_entry_bytes": 20,
                                "archive_max_total_uncompressed_bytes": 30,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))
    fa._attachments_limits.cache_clear()
    try:
        payload = _zip_bytes({"a.txt": b"x" * 50})
        out = process_file_data("limited.zip", payload)
    finally:
        fa._attachments_limits.cache_clear()
    assert out
    first = out[0]
    assert "entry too large" in str(first.get("content") or "").lower()


def test_nested_zip_depth_limit_is_enforced() -> None:
    z4 = _zip_bytes({"deep.txt": b"hello"})
    z3 = _zip_bytes({"z4.zip": z4})
    z2 = _zip_bytes({"z3.zip": z3})
    z1 = _zip_bytes({"z2.zip": z2})
    out = process_file_data("z1.zip", z1)
    assert any("nesting too deep" in str(x.get("content") or "").lower() for x in out)


def test_html_is_cleaned_before_attachment_text() -> None:
    html = b"<html><head><style>.x{display:none}</style></head><body><h1>Title</h1><script>alert(1)</script><p>Hello</p></body></html>"
    out = process_file_data("page.html", html)
    content = str((out[0] if out else {}).get("content") or "")
    assert "Title" in content
    assert "Hello" in content
    assert "alert(1)" not in content
    assert "<h1>" not in content


def test_pdf_summary_contains_page_markers() -> None:
    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, _stream) -> None:
            self.pages = [_Page("P1"), _Page("P2")]

    old = fa.PdfReader
    try:
        fa.PdfReader = _Reader  # type: ignore[assignment]
        out = process_file_data("doc.pdf", b"%PDF")
    finally:
        fa.PdfReader = old  # type: ignore[assignment]
    content = str((out[0] if out else {}).get("content") or "")
    assert "# PDF Summary" in content
    assert "pages: 2" in content
    assert "## Page 1" in content
    assert "## Page 2" in content


def test_zip_unsafe_member_path_is_blocked() -> None:
    payload = _zip_bytes({"../evil.txt": b"x"})
    out = process_file_data("unsafe.zip", payload)
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "zip-error"
    assert "unsafe path" in str(first.get("content") or "").lower()


def test_csv_marks_sampled_when_row_limit_hit() -> None:
    rows = ["c1,c2"] + [f"{i},{i+1}" for i in range(0, 6000)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("big.csv", payload)
    content = str((out[0] if out else {}).get("content") or "")
    assert "sampled: yes" in content


def test_zip_member_name_too_long_is_blocked() -> None:
    payload = _zip_bytes({("a" * 300) + ".txt": b"x"})
    out = process_file_data("unsafe.zip", payload)
    assert out
    first = out[0]
    assert str(first.get("name") or "") == "zip-error"
    assert "unsafe path" in str(first.get("content") or "").lower()


def test_csv_marks_clipped_columns_when_width_limit_hit() -> None:
    columns = [f"c{i}" for i in range(0, 260)]
    header = ",".join(columns)
    row = ",".join(["1"] * len(columns))
    payload = (header + "\n" + row + "\n").encode("utf-8")
    out = process_file_data("wide.csv", payload)
    content = str((out[0] if out else {}).get("content") or "")
    assert "clipped_columns: yes" in content
    assert "cols: 200" in content


def test_csv_marks_clipped_cells_when_cell_content_too_long() -> None:
    long_cell = "x" * 1200
    payload = f"c1,c2\n{long_cell},ok\n".encode("utf-8")
    out = process_file_data("long-cell.csv", payload)
    content = str((out[0] if out else {}).get("content") or "")
    assert "clipped_cells: yes" in content
    assert "...[cell-truncated]" in content


def test_tabular_limits_can_be_overridden_by_config(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "max_rows_read": 2,
                                "max_columns": 2,
                                "max_cell_chars": 10,
                                "large_table_preview_rows": 1,
                                "tool_mode_enabled": True,
                                "tool_mode_min_rows": 3,
                                "tool_mode_max_bytes": 1024 * 1024,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))
    fa._attachments_limits.cache_clear()
    try:
        payload = "c1,c2,c3\n" + ("x" * 40) + ",b,c\n1,2,3\n4,5,6\n"
        out = process_file_data("configured.csv", payload.encode("utf-8"))
    finally:
        fa._attachments_limits.cache_clear()
    content = str((out[0] if out else {}).get("content") or "")
    assert "sampled: yes" in content
    assert "clipped_columns: yes" in content
    assert "clipped_cells: yes" in content
    assert "Preview (first 1 rows)" in content


def test_large_csv_emits_tabular_ref_and_can_query() -> None:
    rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 25050)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("large.csv", payload)
    assert out
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    assert table_id
    got = query_table(
        table_id=table_id,
        columns=["c1", "c2"],
        limit=5,
        offset=0,
        where_contains={"column": "c2", "keyword": "row-12"},
    )
    assert bool(got.get("ok"))
    assert str(got.get("table_id") or "") == table_id
    assert str(got.get("engine") or "") in {"builtin_sqlite", "mcp_sqlite"}


def test_medium_csv_enters_tool_mode_with_default_threshold(tmp_path: Path, monkeypatch) -> None:
    """Isolate from repo ``oclaw.json`` (may raise ``tool_mode_min_rows`` above this test's row count)."""
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "tool_mode_enabled": True,
                                "tool_mode_min_rows": 5000,
                                "tool_mode_max_bytes": 30 * 1024 * 1024,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))
    fa._attachments_limits.cache_clear()
    try:
        rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 6000)]
        payload = ("\n".join(rows)).encode("utf-8")
        out = process_file_data("medium-default.csv", payload)
        tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
        assert tab_refs
    finally:
        fa._attachments_limits.cache_clear()


def test_large_csv_can_aggregate_grouped_sum() -> None:
    rows = ["dept,amount"] + [f"{'A' if i % 2 == 0 else 'B'},{i}" for i in range(0, 25010)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("large2.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    got = aggregate_table(
        table_id=table_id,
        metric="sum",
        target_column="amount",
        group_by="dept",
        top_n=5,
    )
    assert bool(got.get("ok"))
    rows_out = got.get("rows") or []
    assert isinstance(rows_out, list) and len(rows_out) >= 2
    groups = {str(x.get("group") or "") for x in rows_out}
    assert "A" in groups and "B" in groups
    assert str(got.get("engine") or "") in {"builtin_sqlite", "mcp_sqlite"}


def test_query_falls_back_to_builtin_when_mcp_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("AIA_MCP_SQLITE_COMMAND", "nonexistent_mcp_sqlite_binary")
    rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 25020)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("fallback.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    got = query_table(table_id=table_id, columns=["c1"], limit=3, offset=0)
    assert bool(got.get("ok"))
    assert str(got.get("engine") or "") == "builtin_sqlite"


def test_run_tabular_sql_select_works_and_blocks_mutation() -> None:
    rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 25020)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("sql.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    ok = run_table_sql(table_id=table_id, sql='SELECT "c1","c2" FROM rows_data WHERE "c2" LIKE \'%row-12%\'', limit=10)
    assert bool(ok.get("ok"))
    assert int(ok.get("rows_returned") or 0) >= 1
    assert "SELECT" in str(ok.get("executed_sql") or "")
    guard = ok.get("sql_guard") or {}
    assert bool(guard.get("readonly_enforced"))
    assert bool(guard.get("auto_limit_applied"))
    bad = run_table_sql(table_id=table_id, sql="DROP TABLE rows_data", limit=10)
    assert not bool(bad.get("ok"))
    assert str(bad.get("error") or "") == "sql_not_readonly"


def test_run_tabular_sql_timeout_returns_guard(monkeypatch) -> None:
    rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 25020)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("sql-timeout.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    monkeypatch.setenv("AIA_TABULAR_SQL_TIMEOUT_MS", "100")
    slow_sql = (
        "WITH RECURSIVE t(n) AS ("
        "SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n < 5000000"
        ") SELECT SUM(n) FROM t"
    )
    got = run_table_sql(table_id=table_id, sql=slow_sql, limit=200)
    assert not bool(got.get("ok"))
    assert str(got.get("error") or "") == "sql_timeout"
    guard = got.get("sql_guard") or {}
    assert bool(guard.get("timeout_hit"))
    assert int(guard.get("timeout_ms") or 0) == 100


def test_run_tabular_sql_timeout_reads_oclaw_config(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "sql_timeout_ms": 222,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))
    monkeypatch.delenv("AIA_TABULAR_SQL_TIMEOUT_MS", raising=False)
    rows = ["c1,c2"] + [f"{i},row-{i}" for i in range(0, 25020)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("sql-timeout-config.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    got = run_table_sql(table_id=table_id, sql='SELECT "c1" FROM rows_data WHERE "c2" LIKE \'%row-12%\'', limit=10)
    assert bool(got.get("ok"))
    guard = got.get("sql_guard") or {}
    assert int(guard.get("timeout_ms") or 0) == 222


def test_save_workbook_normalizes_duplicate_and_blank_headers() -> None:
    df = pd.DataFrame([["1", "2", "3"]], columns=["", "重复", "重复"])
    meta = save_workbook(attachment_id="aid1", name="dup.xlsx", sheets={"Data": df})
    cols = list(meta.get("columns") or [])
    assert cols[0].startswith("col_")
    assert "重复" in cols
    assert "重复__2" in cols


def test_query_can_target_specific_excel_sheet() -> None:
    s1 = pd.DataFrame([["a", "1"]], columns=["k", "v"])
    s2 = pd.DataFrame([["b", "2"]], columns=["k", "v"])
    meta = save_workbook(attachment_id="aid2", name="multi.xlsx", sheets={"S1": s1, "S2": s2})
    tid = str(meta.get("table_id") or "")
    got = query_table(table_id=tid, sheet="S2", columns=["k", "v"], limit=5, offset=0)
    assert bool(got.get("ok"))
    rows = got.get("rows") or []
    assert rows and str(rows[0].get("k") or "") == "b"


def test_multi_sheet_query_without_sheet_returns_sheet_hint() -> None:
    s1 = pd.DataFrame([["a", "1"]], columns=["k", "v"])
    s2 = pd.DataFrame([["b", "2"]], columns=["k", "v"])
    meta = save_workbook(attachment_id="aid3", name="multi2.xlsx", sheets={"Main": s1, "Backup": s2})
    tid = str(meta.get("table_id") or "")
    got = query_table(table_id=tid, columns=["k", "v"], limit=5, offset=0)
    assert bool(got.get("ok"))
    hint = got.get("sheet_hint") or {}
    assert isinstance(hint, dict)
    names = hint.get("available_sheets") or []
    assert "Main" in names and "Backup" in names
    assert str(hint.get("default_sheet") or "") == "Main"


def test_full_scan_analyzes_all_rows_and_returns_audit() -> None:
    rows = ["dept,score"] + [f"{'A' if i % 2 == 0 else 'B'},{i % 5}" for i in range(0, 25025)]
    payload = ("\n".join(rows)).encode("utf-8")
    out = process_file_data("fullscan.csv", payload)
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    table_id = str(tab_refs[0].get("table_id") or "")
    got = analyze_table_full_scan(table_id=table_id, columns=["dept", "score"], top_values_limit=2)
    assert bool(got.get("ok"))
    assert int(got.get("rows_scanned") or 0) >= 25025
    audit = got.get("scan_audit") or {}
    assert bool(audit.get("full_scan"))
    assert int(audit.get("rows_scanned") or 0) >= 25025
    stats = got.get("column_stats") or []
    assert isinstance(stats, list) and len(stats) == 2
    dept = [x for x in stats if str(x.get("column") or "") == "dept"]
    assert dept
    tops = dept[0].get("top_values") or []
    assert isinstance(tops, list) and len(tops) <= 2


def test_tabular_tools_reject_non_table_id_filename() -> None:
    bad_id = "日志.xlsx"
    q = query_table(table_id=bad_id, columns=["a"], limit=5, offset=0)
    assert not bool(q.get("ok"))
    assert str(q.get("error") or "") == "table_id_invalid_format"

    ag = aggregate_table(table_id=bad_id, metric="count")
    assert not bool(ag.get("ok"))
    assert str(ag.get("error") or "") == "table_id_invalid_format"

    sql = run_table_sql(table_id=bad_id, sql="SELECT 1", limit=5)
    assert not bool(sql.get("ok"))
    assert str(sql.get("error") or "") == "table_id_invalid_format"

    fs = analyze_table_full_scan(table_id=bad_id, columns=["a"], top_values_limit=1)
    assert not bool(fs.get("ok"))
    assert str(fs.get("error") or "") == "table_id_invalid_format"


def test_xlsx_zip_safety_blocks_unsafe_paths() -> None:
    payload = _zip_bytes({"../xl/workbook.xml": b"x"})
    out = process_file_data("bad.xlsx", payload)
    assert out
    first = out[0]
    assert str(first.get("type") or "") == "text"
    assert "unsafe path" in str(first.get("content") or "").lower()


def test_excel_sheet_count_cap_applies_in_tool_mode(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "max_rows_read": 200,
                                "max_columns": 50,
                                "max_cell_chars": 200,
                                "max_excel_sheets": 1,
                                "large_table_preview_rows": 20,
                                "tool_mode_enabled": True,
                                "tool_mode_min_rows": 1,
                                "tool_mode_max_bytes": 10 * 1024 * 1024,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))
    fa._attachments_limits.cache_clear()
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf) as writer:
            pd.DataFrame({"a": ["1", "2"], "b": ["3", "4"]}).to_excel(writer, index=False, sheet_name="S1")
            pd.DataFrame({"a": ["5", "6"], "b": ["7", "8"]}).to_excel(writer, index=False, sheet_name="S2")
        out = process_file_data("multi.xlsx", buf.getvalue())
    finally:
        fa._attachments_limits.cache_clear()
    tab_refs = [x for x in out if isinstance(x, dict) and str(x.get("type") or "") == "tabular_ref"]
    assert tab_refs
    sheets = list(tab_refs[0].get("sheets") or [])
    assert len(sheets) == 1
    notes = [x for x in out if isinstance(x, dict) and str(x.get("name") or "").endswith(".sheet-limit")]
    assert notes


def test_attachment_asset_store_mp4_load_bytes_roundtrip(tmp_path: Path) -> None:
    """Regression: ``load_bytes`` must resolve ``.mp4`` on-disk blobs (not only image extensions)."""
    from svc.files.attachment_assets import AttachmentAssetStore

    ast = AttachmentAssetStore(str(tmp_path))
    payload = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"vid" * 400
    meta = ast.save_bytes(payload, filename="clip.mp4", mime="video/mp4")
    blob, meta2 = ast.load_bytes(meta.attachment_id)
    assert blob == payload
    assert meta2 is not None
    assert meta2.bytes == len(payload)

