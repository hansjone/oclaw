from __future__ import annotations

from threading import Lock

_LOCK = Lock()
_INITIALIZED = False


def init_subagent_registry() -> None:
    """Initialize subagent registry runtime once.

    Python gateway currently keeps this as a lightweight compatibility seam,
    so startup code can mirror the OpenClaw TypeScript bootstrap flow.
    """
    global _INITIALIZED
    with _LOCK:
        if _INITIALIZED:
            return
        _INITIALIZED = True


def is_subagent_registry_initialized() -> bool:
    with _LOCK:
        return _INITIALIZED


def reset_subagent_registry_for_tests() -> None:
    global _INITIALIZED
    with _LOCK:
        _INITIALIZED = False


__all__ = [
    "init_subagent_registry",
    "is_subagent_registry_initialized",
    "reset_subagent_registry_for_tests",
]
