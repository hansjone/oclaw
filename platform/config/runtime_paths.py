from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT


def oclaw_root() -> Path:
    return Path(PROJECT_ROOT).resolve()


def runtime_root() -> Path:
    return (oclaw_root() / "runtime").resolve()


def runtime_skills_root() -> Path:
    """Canonical skills tree lives at repo ``skills/``; ``runtime/skills`` remains a migration fallback."""
    root_skills = (oclaw_root() / "skills").resolve()
    legacy_runtime_skills = (runtime_root() / "skills").resolve()
    if root_skills.is_dir():
        return root_skills
    if legacy_runtime_skills.is_dir():
        return legacy_runtime_skills
    return root_skills


def runtime_hooks_root() -> Path:
    return (runtime_root() / "hooks").resolve()


def runtime_hooks_bundled_root() -> Path:
    return (runtime_hooks_root() / "bundled").resolve()


def runtime_extensions_root() -> Path:
    return (runtime_root() / "extensions").resolve()


def runtime_operations_scripts_root() -> Path:
    return (runtime_root() / "operations" / "scripts").resolve()


def ws_protocol_schemas_root() -> Path:
    return (oclaw_root() / "interfaces" / "ws" / "protocol_schemas").resolve()


__all__ = [
    "oclaw_root",
    "runtime_root",
    "runtime_skills_root",
    "runtime_hooks_root",
    "runtime_hooks_bundled_root",
    "runtime_extensions_root",
    "runtime_operations_scripts_root",
    "ws_protocol_schemas_root",
]

