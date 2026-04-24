from __future__ import annotations

from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.base import ToolSpec


def _require(s: str, name: str) -> str:
    v = (s or "").strip()
    if not v:
        raise ValueError(f"{name} is required")
    return v


def todo_create_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            owner_user_id = _require(str(args.get("owner_user_id") or ""), "owner_user_id")
            title = _require(str(args.get("title") or ""), "title")
            due_at = str(args.get("due_at") or "").strip() or None
            assignee_user_id = str(args.get("assignee_user_id") or "").strip() or None
            store = SqliteStore(db_path())
            row = store.todo_create(
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                title=title,
                due_at=due_at,
                assignee_user_id=assignee_user_id,
            )
            return {"ok": True, "todo": row}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="todo_create",
        description="Create a todo item for a tenant/user.",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "owner_user_id": {"type": "string"},
                "title": {"type": "string"},
                "due_at": {"type": "string", "description": "Optional ISO timestamp or natural text."},
                "assignee_user_id": {"type": "string", "description": "Optional user id to assign."},
            },
            "required": ["tenant_id", "owner_user_id", "title"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write"}),
    )


def todo_list_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            assignee_user_id = str(args.get("assignee_user_id") or "").strip() or None
            status = str(args.get("status") or "open").strip() or None
            limit = int(args.get("limit") or 50)
            store = SqliteStore(db_path())
            rows = store.todo_list(
                tenant_id=tenant_id,
                assignee_user_id=assignee_user_id,
                status=status,
                limit=limit,
            )
            return {"ok": True, "items": rows}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="todo_list",
        description="List todo items by tenant (optionally by assignee and status).",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "assignee_user_id": {"type": "string"},
                "status": {"type": "string", "default": "open"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["tenant_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity"}),
    )


def todo_done_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            todo_id = _require(str(args.get("todo_id") or ""), "todo_id")
            store = SqliteStore(db_path())
            ok = store.todo_set_status(tenant_id=tenant_id, todo_id=todo_id, status="done")
            return {"ok": bool(ok), "todo_id": todo_id}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="todo_done",
        description="Mark a todo item as done.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "todo_id": {"type": "string"}},
            "required": ["tenant_id", "todo_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write"}),
    )


def todo_assign_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            todo_id = _require(str(args.get("todo_id") or ""), "todo_id")
            assignee_user_id = _require(str(args.get("assignee_user_id") or ""), "assignee_user_id")
            store = SqliteStore(db_path())
            ok = store.todo_assign(tenant_id=tenant_id, todo_id=todo_id, assignee_user_id=assignee_user_id)
            return {"ok": bool(ok), "todo_id": todo_id, "assignee_user_id": assignee_user_id}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="todo_assign",
        description="Assign a todo item to a user.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "todo_id": {"type": "string"}, "assignee_user_id": {"type": "string"}},
            "required": ["tenant_id", "todo_id", "assignee_user_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write"}),
    )


__all__ = ["todo_create_tool", "todo_list_tool", "todo_done_tool", "todo_assign_tool"]

