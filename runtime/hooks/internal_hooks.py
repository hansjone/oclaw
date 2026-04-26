from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, MutableMapping, Optional, Sequence, Set, Tuple, Union

log = logging.getLogger("oclaw.hooks")

HookEventType = str
HookAction = str
HookEventKey = str


@dataclass(slots=True)
class HookEvent:
    """
    A lightweight, transport-agnostic hook event.

    This intentionally mirrors the Oclaw internal hook model:
    - handlers may register on "type" or "type:action"
    - failures are isolated per-handler
    """

    type: HookEventType
    action: HookAction
    sessionKey: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: _dt.datetime = field(default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc))
    messages: List[Any] = field(default_factory=list)


HookHandler = Callable[[HookEvent], Union[None, Awaitable[None]]]

_handlers: MutableMapping[HookEventKey, List[HookHandler]] = {}
_enabled_state: Dict[str, bool] = {"enabled": True}


def register_hook(event_key: str, handler: HookHandler) -> None:
    _handlers.setdefault(event_key, []).append(handler)


def unregister_hook(event_key: str, handler: HookHandler) -> None:
    existing = _handlers.get(event_key)
    if not existing:
        return
    try:
        existing.remove(handler)
    except ValueError:
        return
    if not existing:
        _handlers.pop(event_key, None)


def clear_hooks() -> None:
    _handlers.clear()


def set_hooks_enabled(enabled: bool) -> None:
    _enabled_state["enabled"] = bool(enabled)


def get_registered_hook_event_keys() -> List[str]:
    return list(_handlers.keys())


def _has_listeners(event_type: str, action: str) -> bool:
    return bool(_handlers.get(event_type)) or bool(_handlers.get(f"{event_type}:{action}"))


def create_hook_event(
    event_type: HookEventType,
    action: HookAction,
    session_key: str,
    context: Optional[Dict[str, Any]] = None,
) -> HookEvent:
    # Must not use `context or {}` — a caller-supplied empty dict is falsy and would be replaced.
    return HookEvent(
        type=event_type, action=action, sessionKey=session_key, context={} if context is None else context
    )


async def trigger_hook(event: HookEvent) -> None:
    if not _enabled_state["enabled"]:
        return
    if not _has_listeners(event.type, event.action):
        return

    all_handlers: List[HookHandler] = []
    all_handlers.extend(_handlers.get(event.type, []))
    all_handlers.extend(_handlers.get(f"{event.type}:{event.action}", []))

    for handler in all_handlers:
        try:
            res = handler(event)
            if hasattr(res, "__await__"):
                await res  # type: ignore[misc]
        except Exception:
            log.exception("Hook error [%s:%s]", event.type, event.action)

