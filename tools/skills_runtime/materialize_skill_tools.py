from __future__ import annotations

from typing import Any

from oclaw.openclaw_runtime.skills import discover_workspace_skill_manifests
from oclaw.tools.base import ToolSpec


def materialize_executable_skill_tools(*, store: Any | None = None) -> list[ToolSpec]:
    """Convert installed skill manifests with runtime into ToolSpec.

    Tool name equals skill name so the model can call it directly.
    """
    _ = store
    out: list[ToolSpec] = []
    for m in discover_workspace_skill_manifests():
        rt = dict(m.runtime or {}) if isinstance(m.runtime, dict) else {}
        if not rt:
            continue
        tp = str(rt.get("type") or "").strip().lower()
        entry = str(rt.get("entry") or "").strip()
        if not tp or not entry:
            continue
        schema = rt.get("schema") if isinstance(rt.get("schema"), dict) else {"type": "object", "additionalProperties": True}
        name = str(m.name or "").strip()
        if not name:
            continue

        def _handler(args: dict[str, Any], *, _manifest=m, _rt=rt) -> dict[str, Any]:
            from oclaw.tools.skills_runtime.subprocess_exec import run_skill_runtime_entry

            return run_skill_runtime_entry(
                skill_name=str(_manifest.name or ""),
                skill_dir=str(_manifest.skill_dir or ""),
                runtime=dict(_rt),
                args=dict(args or {}),
            )

        out.append(
            ToolSpec(
                name=name,
                description=str(m.description or ""),
                parameters=dict(schema),
                handler=_handler,
                tags=frozenset({"skill", "openclaw", "runtime"}),
                risk_level="high",
                timeout_s=60.0,
            )
        )
    return out


__all__ = ["materialize_executable_skill_tools"]

