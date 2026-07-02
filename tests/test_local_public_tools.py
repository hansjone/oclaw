from __future__ import annotations

import tempfile
from pathlib import Path

from runtime.tools.catalog import default_registry
from runtime.tools.public.local_sdk import LocalAdapter
from runtime.tools.public.edit_file_tool import edit_file_tool
from runtime.tools.public.run_command_tool import run_command_tool
from runtime.tools.public.read_file_tool import read_file_tool
from runtime.tools.public.write_file_tool import write_file_tool
from runtime.tools.public_registry import clear_public_tool_cache
from runtime.tools.public.list_directory_tool import list_directory_tool
from runtime.tools.public.search_files_tool import search_files_tool
from runtime.tools.public.get_cwd_tool import get_cwd_tool
from runtime.tools.public.get_env_tool import get_env_tool
from runtime.tools.public.set_env_tool import set_env_tool


def test_local_public_read_tool_visible_by_default() -> None:
    clear_public_tool_cache()
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "schedule_create" in names
    assert "read_file" in names
    assert "list_directory" in names
    assert "search_files" in names
    assert "get_cwd" in names
    assert "get_env" in names
    assert "list_processes" in names
    assert "run_command" not in names
    assert "write_file" not in names
    assert "edit_file" not in names
    assert "mkdir" not in names
    assert "delete_file" not in names
    assert "move_file" not in names
    assert "set_env" not in names
    assert "kill_process" not in names


def test_local_public_high_risk_tools_visible_when_enabled(monkeypatch) -> None:
    clear_public_tool_cache()
    monkeypatch.setenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", "1")
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "read_file" in names
    assert "list_directory" in names
    assert "search_files" in names
    assert "get_cwd" in names
    assert "get_env" in names
    assert "list_processes" in names
    assert "run_command" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "mkdir" in names
    assert "delete_file" in names
    assert "move_file" in names
    assert "set_env" in names
    assert "kill_process" in names


def test_local_adapter_backend_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIA_ENABLE_RUN_COMMAND", "1")
    adapter = LocalAdapter()
    out_w = adapter.write_file(path="a.txt", content="hello\nworld\n")
    assert out_w.get("ok") is True
    out = adapter.edit_file(path="a.txt", search="hello", replace="hi")
    assert out.get("ok") is True
    out2 = adapter.run_command(command="echo hi", timeout=10)
    assert out2.get("ok") is True
    assert "hi" in str(out2.get("stdout") or "").lower()


def test_run_command_tool_handler(monkeypatch) -> None:
    class _Adapter:
        def run_command(self, *, command: str, cwd: str | None = None, timeout: int = 300):
            return {"ok": True, "command": command, "cwd": cwd, "timeout": timeout}

    monkeypatch.setattr("runtime.tools.public.run_command_tool.get_local_adapter", lambda: _Adapter())
    spec = run_command_tool()
    out = spec.handler({"command": "echo hi", "cwd": "repo", "timeout": 9})
    assert out.get("ok") is True
    assert out.get("command") == "echo hi"
    assert out.get("cwd") == "repo"
    assert out.get("timeout") == 9


def test_edit_file_tool_handler(monkeypatch) -> None:
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

    monkeypatch.setattr("runtime.tools.public.edit_file_tool.get_local_adapter", lambda: _Adapter())
    spec = edit_file_tool()
    out = spec.handler({"path": "a.py", "search": "foo", "replace": "bar"})
    assert out.get("ok") is True
    assert out.get("path") == "a.py"
    assert out.get("search") == "foo"
    assert out.get("replace") == "bar"


def test_local_tool_integration_roundtrip(monkeypatch) -> None:
    run_spec = run_command_tool()
    read_spec = read_file_tool()
    write_spec = write_file_tool()
    edit_spec = edit_file_tool()

    tmpdir = Path(tempfile.mkdtemp(prefix="local_it_"))
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmpdir))
    monkeypatch.setenv("AIA_ENABLE_RUN_COMMAND", "1")
    target_rel = "it_sample.txt"

    out_write = write_spec.handler({"path": "it_sample.txt", "content": "line1\nline2\n", "mode": "overwrite"})
    assert out_write.get("ok") is True, out_write

    out_read_before = read_spec.handler({"path": target_rel, "offset": 1, "limit": 10})
    assert out_read_before.get("ok") is True, out_read_before
    assert "line2" in str(out_read_before.get("content") or "")

    out_edit = edit_spec.handler({"path": target_rel, "search": "line2", "replace": "line2_edited"})
    assert out_edit.get("ok") is True, out_edit

    out_read_after = read_spec.handler({"path": target_rel, "offset": 1, "limit": 10})
    assert out_read_after.get("ok") is True, out_read_after
    assert "line2_edited" in str(out_read_after.get("content") or "")

    out_run = run_spec.handler({"command": "python -c \"print(12345)\"", "cwd": str(tmpdir), "timeout": 20})
    assert out_run.get("ok") is True, out_run
    stdout = str(out_run.get("stdout") or "")
    assert "12345" in stdout


def test_p1_p2_read_tools_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    # list_directory
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "a.txt").write_text("hello", encoding="utf-8")
    out_ls = list_directory_tool().handler({"path": "d", "max_entries": 50})
    assert out_ls.get("ok") is True
    assert any(e.get("name") == "a.txt" for e in (out_ls.get("entries") or []))
    # search_files
    out_s = search_files_tool().handler({"pattern": "hell", "root": "d", "regex": False})
    assert out_s.get("ok") is True
    assert (out_s.get("count") or 0) >= 1
    # get_cwd
    out_cwd0 = get_cwd_tool().handler({})
    assert out_cwd0.get("ok") is True
    assert str(out_cwd0.get("cwd") or "").replace("\\", "/").rstrip("/") == str(tmp_path).replace("\\", "/").rstrip("/")
    # get_env / set_env
    out_get0 = get_env_tool().handler({"key": "LOCAL_PUBLIC_TOOLS_TEST_KEY", "default": "x"})
    assert out_get0.get("ok") is True
    out_set = set_env_tool().handler({"key": "LOCAL_PUBLIC_TOOLS_TEST_KEY", "value": "y"})
    assert out_set.get("ok") is True
    out_get1 = get_env_tool().handler({"key": "LOCAL_PUBLIC_TOOLS_TEST_KEY"})
    assert out_get1.get("ok") is True
    assert out_get1.get("value") == "y"


def test_get_cwd_returns_workspace_root_when_at_data_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "data" / "workspace").mkdir(parents=True, exist_ok=True)
    adapter = LocalAdapter()

    out_cd = adapter.cd(cwd="data/workspace")
    assert out_cd.get("ok") is True

    out_cwd = adapter.get_cwd()
    assert out_cwd.get("ok") is True
    norm = str(out_cwd.get("cwd") or "").replace("\\", "/").rstrip("/")
    assert norm == str(tmp_path).replace("\\", "/").rstrip("/")


def test_get_cwd_returns_workspace_root_even_after_cd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "subdir").mkdir(parents=True, exist_ok=True)
    adapter = LocalAdapter()

    out_cd = adapter.cd(cwd="subdir")
    assert out_cd.get("ok") is True

    out_cwd = adapter.get_cwd()
    assert out_cwd.get("ok") is True
    norm = str(out_cwd.get("cwd") or "").replace("\\", "/").rstrip("/")
    assert norm == str(tmp_path).replace("\\", "/").rstrip("/")


def test_run_command_does_not_follow_cd_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIA_ENABLE_RUN_COMMAND", "1")
    (tmp_path / "data" / "workspace").mkdir(parents=True, exist_ok=True)
    (tmp_path / "subdir").mkdir(parents=True, exist_ok=True)
    (tmp_path / "subdir" / "echo_dir.py").write_text(
        "import os\nprint(os.path.basename(os.getcwd()))\n",
        encoding="utf-8",
    )

    adapter = LocalAdapter()
    out_cd = adapter.cd(cwd="subdir")
    assert out_cd.get("ok") is True

    out_run = adapter.run_command(command='python -c "import os; print(os.path.basename(os.getcwd()))"', timeout=20)
    assert out_run.get("ok") is True, out_run
    # If run_command follows cd state this would be "subdir"; default should be workspace root.
    assert str(out_run.get("cwd") or "").replace("\\", "/").rstrip("/") == str(tmp_path).replace("\\", "/").rstrip("/")


def test_run_command_reads_db_toggle_without_ops_db_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("OPS_ASSISTANT_DB_PATH", raising=False)
    monkeypatch.setenv("AIA_ENABLE_RUN_COMMAND", "0")

    db_file = tmp_path / "ops.sqlite"
    from svc.persistence.sqlite_store import SqliteStore

    SqliteStore(str(db_file)).set_setting("AIA_ENABLE_RUN_COMMAND", "1")
    monkeypatch.setattr("svc.config.paths.db_path", lambda: str(db_file))

    out = LocalAdapter().run_command(command="echo hi", timeout=10)
    assert out.get("ok") is True, out

