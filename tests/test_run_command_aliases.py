from __future__ import annotations

from runtime.tools.public.run_command_tool import run_command_tool
from runtime.tools.tool_validation import filter_arguments_to_schema, validate_tool_arguments


def test_run_command_accepts_cmd_alias(monkeypatch) -> None:
    calls: list[dict] = []

    class _Adapter:
        def run_command(self, *, command: str, cwd=None, timeout: int = 300):
            calls.append({"command": command, "cwd": cwd, "timeout": timeout})
            return {"ok": True, "stdout": "hi", "stderr": "", "exit_code": 0}

    monkeypatch.setattr(
        "runtime.tools.public.run_command_tool.get_local_adapter",
        lambda: _Adapter(),
    )
    spec = run_command_tool()
    args = {"cmd": "echo hi", "timeout": 10}
    filtered = filter_arguments_to_schema(spec.parameters, args)
    ok, err = validate_tool_arguments(spec.parameters, filtered)
    assert ok, err
    out = spec.handler(filtered)
    assert out.get("ok") is True
    assert calls[0]["command"] == "echo hi"
