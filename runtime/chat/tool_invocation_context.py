from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_tool_lane_owner: ContextVar[str | None] = ContextVar("tool_lane_owner", default=None)
_tool_lane_session: ContextVar[str | None] = ContextVar("tool_lane_session", default=None)
_tool_workspace_lane_role: ContextVar[str | None] = ContextVar("tool_workspace_lane_role", default=None)


@contextmanager
def tool_workspace_lane_scope(
    *,
    workspace_owner_session_id: str | None,
    session_id: str | None,
    workspace_lane_role: str | None = None,
) -> Iterator[None]:
    o = str(workspace_owner_session_id or "").strip() or None
    s = str(session_id or "").strip() or None
    r = str(workspace_lane_role or "").strip().lower() or None
    t_o = _tool_lane_owner.set(o)
    t_s = _tool_lane_session.set(s)
    t_r = _tool_workspace_lane_role.set(r)
    try:
        yield
    finally:
        _tool_lane_owner.reset(t_o)
        _tool_lane_session.reset(t_s)
        _tool_workspace_lane_role.reset(t_r)


def current_tool_lane_sessions() -> tuple[str | None, str | None]:
    return _tool_lane_owner.get(), _tool_lane_session.get()


def current_tool_workspace_lane_role() -> str | None:
    return _tool_workspace_lane_role.get()


__all__ = [
    "current_tool_lane_sessions",
    "current_tool_workspace_lane_role",
    "tool_workspace_lane_scope",
]
