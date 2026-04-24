from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_AGENT_ID = "default"


def _normalize_agent_id(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return DEFAULT_AGENT_ID
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    normalized = "".join(out).strip("-_")
    return normalized or DEFAULT_AGENT_ID


def list_agent_entries(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    agents = (cfg.get("agents") or {}) if isinstance(cfg, dict) else {}
    entries = agents.get("list")
    if not isinstance(entries, list):
        return []
    return [x for x in entries if isinstance(x, dict)]


def list_agent_ids(cfg: dict[str, Any]) -> list[str]:
    entries = list_agent_entries(cfg)
    if not entries:
        return [DEFAULT_AGENT_ID]
    seen: set[str] = set()
    ids: list[str] = []
    for entry in entries:
        aid = _normalize_agent_id(entry.get("id"))
        if aid in seen:
            continue
        seen.add(aid)
        ids.append(aid)
    return ids or [DEFAULT_AGENT_ID]


def resolve_default_agent_id(cfg: dict[str, Any]) -> str:
    entries = list_agent_entries(cfg)
    if not entries:
        return DEFAULT_AGENT_ID
    defaults = [x for x in entries if bool(x.get("default"))]
    chosen = (defaults[0] if defaults else entries[0]).get("id")
    return _normalize_agent_id(chosen)


def _resolve_agent_entry(cfg: dict[str, Any], agent_id: str) -> dict[str, Any] | None:
    target = _normalize_agent_id(agent_id)
    for entry in list_agent_entries(cfg):
        if _normalize_agent_id(entry.get("id")) == target:
            return entry
    return None


def resolve_agent_id_from_session_key(session_key: str | None) -> str:
    text = str(session_key or "").strip()
    if not text:
        return DEFAULT_AGENT_ID
    prefix = text.split(":", 1)[0].strip()
    return _normalize_agent_id(prefix)


def resolve_session_agent_ids(
    *,
    session_key: str | None = None,
    config: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> dict[str, str]:
    cfg = config if isinstance(config, dict) else {}
    default_agent_id = resolve_default_agent_id(cfg)
    explicit_agent_id = _normalize_agent_id(agent_id) if str(agent_id or "").strip() else None
    session_agent_id = explicit_agent_id or resolve_agent_id_from_session_key(session_key) or default_agent_id
    return {"default_agent_id": default_agent_id, "session_agent_id": session_agent_id}


def resolve_session_agent_id(
    *,
    session_key: str | None = None,
    config: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> str:
    return resolve_session_agent_ids(session_key=session_key, config=config, agent_id=agent_id)["session_agent_id"]


def _normalize_path_for_comparison(input_path: str) -> Path:
    raw = str(input_path or "").replace("\x00", "").strip() or "."
    p = Path(raw).expanduser()
    try:
        p = p.resolve(strict=False)
    except Exception:
        pass
    norm = str(p)
    if os.name == "nt":
        norm = norm.lower()
    return Path(norm)


def _is_path_within_root(candidate_path: Path, root_path: Path) -> bool:
    try:
        candidate_path.relative_to(root_path)
        return True
    except ValueError:
        return False


def resolve_agent_workspace_dir(cfg: dict[str, Any], agent_id: str) -> str:
    aid = _normalize_agent_id(agent_id)
    agents_cfg = (cfg.get("agents") or {}) if isinstance(cfg, dict) else {}
    defaults = (agents_cfg.get("defaults") or {}) if isinstance(agents_cfg, dict) else {}
    entry = _resolve_agent_entry(cfg, aid) or {}

    configured_workspace = str(entry.get("workspace") or "").strip()
    if configured_workspace:
        return str(Path(configured_workspace))

    fallback_workspace = str(defaults.get("workspace") or "").strip()
    default_agent_id = resolve_default_agent_id(cfg)
    if aid == default_agent_id:
        if fallback_workspace:
            return str(Path(fallback_workspace))
        return str(Path("."))

    if fallback_workspace:
        return str(Path(fallback_workspace) / aid)

    state_dir = str(os.getenv("OCLAW_STATE_DIR") or ".oclaw").strip() or ".oclaw"
    return str(Path(state_dir) / f"workspace-{aid}")


def resolve_agent_ids_by_workspace_path(cfg: dict[str, Any], workspace_path: str) -> list[str]:
    target = _normalize_path_for_comparison(workspace_path)
    matches: list[tuple[str, Path, int]] = []
    for idx, aid in enumerate(list_agent_ids(cfg)):
        ws = _normalize_path_for_comparison(resolve_agent_workspace_dir(cfg, aid))
        if not _is_path_within_root(target, ws):
            continue
        matches.append((aid, ws, idx))
    matches.sort(key=lambda row: (-len(str(row[1])), row[2]))
    return [x[0] for x in matches]


def resolve_agent_id_by_workspace_path(cfg: dict[str, Any], workspace_path: str) -> str | None:
    ids = resolve_agent_ids_by_workspace_path(cfg, workspace_path)
    return ids[0] if ids else None


__all__ = [
    "DEFAULT_AGENT_ID",
    "list_agent_entries",
    "list_agent_ids",
    "resolve_agent_id_by_workspace_path",
    "resolve_agent_id_from_session_key",
    "resolve_agent_ids_by_workspace_path",
    "resolve_session_agent_id",
    "resolve_session_agent_ids",
    "resolve_agent_workspace_dir",
    "resolve_default_agent_id",
]
