from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from runtime.agent_context import build_role_system_context
from runtime.workspaces.experts import specialist_registry_snapshot


SpecialistId = str
AgentRoleId = str
MANAGER_AGENT_ID: AgentRoleId = "manager"
AGENT_PROFILE_BINDINGS_KEY = "agent_profile_bindings"


@dataclass(frozen=True)
class SpecialistConfig:
    specialist_id: SpecialistId
    expert_name: str
    default_tool_tags: frozenset[str] | None


SPECIALISTS: dict[SpecialistId, SpecialistConfig] = {
    "ops": SpecialistConfig(
        specialist_id="ops",
        expert_name="network_ops+memory",
        default_tool_tags=None,
    ),
    "generalist": SpecialistConfig(
        specialist_id="generalist",
        expert_name="generalist+workspace+productivity+memory",
        default_tool_tags=None,
    ),
    "memory": SpecialistConfig(
        specialist_id="memory",
        expert_name="memory",
        default_tool_tags=None,
    ),
    "image": SpecialistConfig(
        specialist_id="image",
        # Vision turns attach pixels in-message; gateway executor exposes no tools (see factory).
        expert_name="image",
        default_tool_tags=None,
    ),
    "video": SpecialistConfig(
        specialist_id="video",
        expert_name="video",
        default_tool_tags=None,
    ),
}

def discover_specialist_ids() -> tuple[SpecialistId, ...]:
    rows = specialist_registry_snapshot(base_order=("generalist", "ops", "memory", "image", "video"))
    return tuple(str(x.get("id") or "").strip().lower() for x in rows if str(x.get("id") or "").strip())


def specialist_ids() -> tuple[SpecialistId, ...]:
    return discover_specialist_ids()


def agent_role_ids() -> tuple[AgentRoleId, ...]:
    return (MANAGER_AGENT_ID, *specialist_ids())


def expert_name_for_specialist(specialist_id: SpecialistId) -> str:
    sid = normalize_specialist_id(specialist_id)
    cfg = SPECIALISTS.get(sid)
    if cfg is None:
        # Unknown dynamic specialists default to least-privilege tools.
        return "generalist"
    return cfg.expert_name


def default_tool_tags_for_specialist(specialist_id: SpecialistId) -> frozenset[str] | None:
    sid = normalize_specialist_id(specialist_id)
    cfg = SPECIALISTS.get(sid) or SPECIALISTS["generalist"]
    return cfg.default_tool_tags


def default_system_prefix_for_specialist(specialist_id: SpecialistId, lang: str = "zh") -> str:
    sid = normalize_specialist_id(specialist_id)
    return build_role_system_context(sid, lang=(lang or "zh").strip().lower())


def model_role_for_specialist(specialist_id: SpecialistId) -> AgentRoleId:
    sid = normalize_specialist_id(specialist_id)
    if sid in specialist_ids():
        return sid
    return "generalist"


def normalize_specialist_id(specialist_id: SpecialistId | None) -> SpecialistId:
    sid = (specialist_id or "").strip().lower()
    if sid in SPECIALISTS:
        return sid
    if sid in discover_specialist_ids():
        return sid
    return "generalist"


def empty_agent_profile_bindings() -> dict[AgentRoleId, str]:
    return {rid: "" for rid in agent_role_ids()}


def parse_agent_profile_bindings(raw: str | None) -> dict[AgentRoleId, str]:
    out = empty_agent_profile_bindings()
    text = (raw or "").strip()
    if not text:
        return out
    try:
        obj = json.loads(text)
    except Exception:
        return out
    if not isinstance(obj, dict):
        return out
    for rid in agent_role_ids():
        v = obj.get(rid)
        if v is None:
            continue
        s = str(v).strip()
        out[rid] = s
    return out


def dump_agent_profile_bindings(bindings: dict[AgentRoleId, Any]) -> str:
    raw = {}
    for rid in agent_role_ids():
        v = bindings.get(rid) if isinstance(bindings, dict) else None
        raw[rid] = str(v).strip() if v is not None else ""
    return json.dumps(raw, ensure_ascii=False)


__all__ = [
    "AGENT_PROFILE_BINDINGS_KEY",
    "AgentRoleId",
    "agent_role_ids",
    "dump_agent_profile_bindings",
    "empty_agent_profile_bindings",
    "MANAGER_AGENT_ID",
    "SpecialistConfig",
    "SpecialistId",
    "SPECIALISTS",
    "specialist_ids",
    "default_system_prefix_for_specialist",
    "default_tool_tags_for_specialist",
    "discover_specialist_ids",
    "expert_name_for_specialist",
    "model_role_for_specialist",
    "normalize_specialist_id",
    "parse_agent_profile_bindings",
]
