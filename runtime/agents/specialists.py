from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from oclaw.runtime.agent_context import build_role_system_context
from oclaw.runtime.workspaces.experts import discover_specialist_ids_from_workspaces


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
        expert_name="network_ops",
        default_tool_tags=None,
    ),
    "generalist": SpecialistConfig(
        specialist_id="generalist",
        expert_name="generalist+workspace+productivity",
        default_tool_tags=None,
    ),
    "image": SpecialistConfig(
        specialist_id="image",
        # image specialist currently reuses generalist expert tool registry,
        # including image_edit tool.
        expert_name="generalist",
        default_tool_tags=None,
    ),
    "memory": SpecialistConfig(
        specialist_id="memory",
        expert_name="memory",
        default_tool_tags=None,
    ),
}

def discover_specialist_ids() -> tuple[SpecialistId, ...]:
    return discover_specialist_ids_from_workspaces(base_order=("generalist", "ops", "image", "memory"))


SPECIALIST_IDS: tuple[SpecialistId, ...] = discover_specialist_ids()
AGENT_ROLE_IDS: tuple[AgentRoleId, ...] = (MANAGER_AGENT_ID, *SPECIALIST_IDS)


def expert_name_for_specialist(specialist_id: SpecialistId) -> str:
    sid = normalize_specialist_id(specialist_id)
    cfg = SPECIALISTS.get(sid) or SPECIALISTS["generalist"]
    return cfg.expert_name


def default_tool_tags_for_specialist(specialist_id: SpecialistId) -> frozenset[str] | None:
    sid = normalize_specialist_id(specialist_id)
    cfg = SPECIALISTS.get(sid) or SPECIALISTS["generalist"]
    return cfg.default_tool_tags


def default_system_prefix_for_specialist(specialist_id: SpecialistId, lang: str = "zh") -> str:
    sid = normalize_specialist_id(specialist_id)
    _ = (lang or "zh").strip().lower()
    return build_role_system_context(sid)


def model_role_for_specialist(specialist_id: SpecialistId) -> AgentRoleId:
    sid = normalize_specialist_id(specialist_id)
    if sid in SPECIALIST_IDS:
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
    return {rid: "" for rid in AGENT_ROLE_IDS}


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
    for rid in AGENT_ROLE_IDS:
        v = obj.get(rid)
        if v is None:
            continue
        s = str(v).strip()
        out[rid] = s
    return out


def dump_agent_profile_bindings(bindings: dict[AgentRoleId, Any]) -> str:
    raw = {}
    for rid in AGENT_ROLE_IDS:
        v = bindings.get(rid) if isinstance(bindings, dict) else None
        raw[rid] = str(v).strip() if v is not None else ""
    return json.dumps(raw, ensure_ascii=False)


__all__ = [
    "AGENT_PROFILE_BINDINGS_KEY",
    "AGENT_ROLE_IDS",
    "AgentRoleId",
    "dump_agent_profile_bindings",
    "empty_agent_profile_bindings",
    "MANAGER_AGENT_ID",
    "SpecialistConfig",
    "SpecialistId",
    "SPECIALISTS",
    "SPECIALIST_IDS",
    "default_system_prefix_for_specialist",
    "default_tool_tags_for_specialist",
    "discover_specialist_ids",
    "expert_name_for_specialist",
    "model_role_for_specialist",
    "normalize_specialist_id",
    "parse_agent_profile_bindings",
]
