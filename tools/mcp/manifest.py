from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class McpServerManifest:
    server_id: str
    source_type: str  # github|npm|pypi
    source_ref: str
    version: str = ""
    entry_command: str = ""
    entry_args: list[str] = field(default_factory=list)
    env_schema: dict[str, Any] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    risk_level: str = "high"
    enabled: bool = False
    timeout_s: float = 30.0

