"""
Public hooks API surface.

Design contract:
- Typed-first internals: loaders/policy/config operate on `HookEntry`.
- Compatibility wrappers: `_compat` helpers accept legacy dict entries.
- External callers should migrate to typed APIs over time; wrappers remain for
  incremental rollout and backward compatibility.
"""

from .internal_hooks import (
    HookEvent,
    HookHandler,
    clear_hooks,
    create_hook_event,
    get_registered_hook_event_keys,
    register_hook,
    set_hooks_enabled,
    trigger_hook,
    unregister_hook,
)

from .loader import load_internal_hooks
from .config import should_include_hook, should_include_hook_compat
from .policy import resolve_hook_entries_compat
from .hooks_status import build_workspace_hook_status
from .eligibility_from_metadata import hook_eligibility_from_message_metadata

__all__ = [
    "HookEvent",
    "HookHandler",
    "register_hook",
    "unregister_hook",
    "clear_hooks",
    "get_registered_hook_event_keys",
    "set_hooks_enabled",
    "trigger_hook",
    "create_hook_event",
    "load_internal_hooks",
    "should_include_hook",
    "should_include_hook_compat",
    "resolve_hook_entries_compat",
    "build_workspace_hook_status",
    "hook_eligibility_from_message_metadata",
]

