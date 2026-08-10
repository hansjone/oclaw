from __future__ import annotations

from pathlib import Path

from runtime.tools.public.write_file_tool import write_file_tool
from runtime.tools.tool_validation import filter_arguments_to_schema, validate_tool_arguments


def test_write_file_accepts_filename_alias(tmp_path, monkeypatch) -> None:
    target = tmp_path / "workspace" / "note.txt"
    monkeypatch.setattr(
        "runtime.tools.public.write_file_tool.resolve_workspace_path",
        lambda raw: target,
    )
    spec = write_file_tool()
    out = spec.handler({"filename": "note.txt", "text": "hello"})
    assert out.get("ok") is True
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_file_schema_allows_aliases() -> None:
    spec = write_file_tool()
    args = {"file": "a.txt", "content": "x"}
    filtered = filter_arguments_to_schema(spec.parameters, args)
    ok, err = validate_tool_arguments(spec.parameters, filtered)
    assert ok, err
    assert "file" in filtered


def test_write_file_path_required_message() -> None:
    spec = write_file_tool()
    out = spec.handler({})
    assert out.get("ok") is False
    assert out.get("error") == "path_required"
    assert "example" in out


def test_write_file_defaults_path_when_content_only(tmp_path, monkeypatch) -> None:
    def _resolve(raw: str):
        return tmp_path / "workspace" / str(raw).replace("\\", "/").lstrip("/")

    monkeypatch.setattr(
        "runtime.tools.public.write_file_tool.resolve_workspace_path",
        _resolve,
    )
    spec = write_file_tool()
    out = spec.handler({"content": "hello-auto"})
    assert out.get("ok") is True
    assert out.get("auto_path") is True
    path = Path(str(out.get("path") or ""))
    assert path.name.startswith("write_")
    assert path.read_text(encoding="utf-8") == "hello-auto"
