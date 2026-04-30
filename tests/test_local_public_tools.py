from __future__ import annotations

import tempfile
from pathlib import Path

from oclaw.runtime.tools.catalog import default_registry
from oclaw.runtime.tools.local_sdk.adapter import LocalAdapter
from oclaw.runtime.tools.public.local_edit_file_tool import local_edit_file_tool
from oclaw.runtime.tools.public.local_read_file_tool import local_read_file_tool
from oclaw.runtime.tools.public.local_run_command_tool import local_run_command_tool
from oclaw.runtime.tools.public.local_write_file_tool import local_write_file_tool
from oclaw.runtime.tools.public_registry import clear_public_tool_cache


def test_local_public_read_tool_visible_by_default() -> None:
    clear_public_tool_cache()
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "local_read_file" in names
    assert "local_run_command" not in names
    assert "local_write_file" not in names
    assert "local_edit_file" not in names


def test_local_public_high_risk_tools_visible_when_enabled(monkeypatch) -> None:
    clear_public_tool_cache()
    monkeypatch.setenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", "1")
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "local_read_file" in names
    assert "local_run_command" in names
    assert "local_write_file" in names
    assert "local_edit_file" in names


def test_local_adapter_backend_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    adapter = LocalAdapter()
    out_w = adapter.write_file(path="a.txt", content="hello\nworld\n")
    assert out_w.get("ok") is True
    out = adapter.edit_file(path="a.txt", search="hello", replace="hi")
    assert out.get("ok") is True
    out2 = adapter.run_command(command="echo hi", timeout=10)
    assert out2.get("ok") is True
    assert "hi" in str(out2.get("stdout") or "").lower()


def test_local_run_command_tool_handler(monkeypatch) -> None:
    class _Adapter:
        def run_command(self, *, command: str, cwd: str | None = None, timeout: int = 30):
            return {"ok": True, "command": command, "cwd": cwd, "timeout": timeout}

    monkeypatch.setattr("oclaw.runtime.tools.public.local_run_command_tool.get_local_adapter", lambda: _Adapter())
    spec = local_run_command_tool()
    out = spec.handler({"command": "echo hi", "cwd": "repo", "timeout": 9})
    assert out.get("ok") is True
    assert out.get("command") == "echo hi"
    assert out.get("cwd") == "repo"
    assert out.get("timeout") == 9


def test_local_read_file_tool_handler(monkeypatch) -> None:
    class _Adapter:
        def read_file(self, *, path: str, start_line: int | None = None, end_line: int | None = None):
            return {"ok": True, "path": path, "start_line": start_line, "end_line": end_line}

    monkeypatch.setattr("oclaw.runtime.tools.public.local_read_file_tool.get_local_adapter", lambda: _Adapter())
    spec = local_read_file_tool()
    out = spec.handler({"path": "a.py", "start_line": 2, "end_line": 5})
    assert out.get("ok") is True
    assert out.get("path") == "a.py"
    assert out.get("start_line") == 2
    assert out.get("end_line") == 5


def test_local_write_file_tool_handler(monkeypatch) -> None:
    class _Adapter:
        def write_file(self, *, path: str, content: str, mode: str = "overwrite"):
            return {"ok": True, "path": path, "content": content, "mode": mode}

    monkeypatch.setattr("oclaw.runtime.tools.public.local_write_file_tool.get_local_adapter", lambda: _Adapter())
    spec = local_write_file_tool()
    out = spec.handler({"path": "a.py", "content": "x=1", "mode": "append"})
    assert out.get("ok") is True
    assert out.get("path") == "a.py"
    assert out.get("content") == "x=1"
    assert out.get("mode") == "append"


def test_local_edit_file_tool_handler(monkeypatch) -> None:
    class _Adapter:
        def edit_file(
            self,
            *,
            path: str,
            search: str | None = None,
            replace: str | None = None,
            start_line: int | None = None,
            end_line: int | None = None,
            replacement: str | None = None,
        ):
            return {
                "ok": True,
                "path": path,
                "search": search,
                "replace": replace,
                "start_line": start_line,
                "end_line": end_line,
                "replacement": replacement,
            }

    monkeypatch.setattr("oclaw.runtime.tools.public.local_edit_file_tool.get_local_adapter", lambda: _Adapter())
    spec = local_edit_file_tool()
    out = spec.handler({"path": "a.py", "search": "foo", "replace": "bar"})
    assert out.get("ok") is True
    assert out.get("path") == "a.py"
    assert out.get("search") == "foo"
    assert out.get("replace") == "bar"


def test_local_tool_integration_roundtrip(monkeypatch) -> None:
    run_spec = local_run_command_tool()
    read_spec = local_read_file_tool()
    write_spec = local_write_file_tool()
    edit_spec = local_edit_file_tool()

    tmpdir = Path(tempfile.mkdtemp(prefix="local_it_"))
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmpdir))
    target = tmpdir / "it_sample.txt"

    out_write = write_spec.handler({"path": str(target), "content": "line1\nline2\n", "mode": "overwrite"})
    assert out_write.get("ok") is True, out_write

    out_read_before = read_spec.handler({"path": str(target), "start_line": 1, "end_line": 10})
    assert out_read_before.get("ok") is True, out_read_before
    assert "line2" in str(out_read_before.get("content") or "")

    out_edit = edit_spec.handler({"path": str(target), "search": "line2", "replace": "line2_edited"})
    assert out_edit.get("ok") is True, out_edit

    out_read_after = read_spec.handler({"path": str(target), "start_line": 1, "end_line": 10})
    assert out_read_after.get("ok") is True, out_read_after
    assert "line2_edited" in str(out_read_after.get("content") or "")

    out_run = run_spec.handler({"command": "python -c \"print(12345)\"", "cwd": str(tmpdir), "timeout": 20})
    assert out_run.get("ok") is True, out_run
    stdout = str(out_run.get("stdout") or "")
    assert "12345" in stdout

