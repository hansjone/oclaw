from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolRateLimit:
    """Best-effort per-tool rate limiting metadata (enforced by runtime when implemented)."""

    # tokens per window (simple leaky bucket style); None means unlimited.
    limit: int | None = None
    window_s: int = 60


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    tags: frozenset[str] = field(default_factory=frozenset)
    # Contract metadata (non-OpenAI; used by orchestrator/runtime)
    version: str = "v1"
    risk_level: str = "low"  # low|high (extendable)
    timeout_s: float | None = None
    rate_limit: ToolRateLimit | None = None
    required_permissions: frozenset[str] = field(default_factory=frozenset)
    execution_mode: str = "in_process"  # in_process|subprocess (best-effort)
    #: If true, may run in parallel with other consecutive read-only tools (cc-mini-style batching).
    read_only: bool = False

    def is_read_only(self) -> bool:
        """Compatibility helper mirroring cc-mini Tool.is_read_only()."""
        return bool(self.read_only)

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec] | None = None):
        self._tools: dict[str, ToolSpec] = {}
        self._openai_tools_cache: list[dict[str, Any]] | None = None
        if tools:
            for t in tools:
                self.register(t)

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool
        self._openai_tools_cache = None

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def as_openai_tools(self) -> list[dict[str, Any]]:
        if self._openai_tools_cache is None:
            self._openai_tools_cache = [t.as_openai_tool() for t in self.list()]
        return list(self._openai_tools_cache)


__all__ = [
    "ToolHandler",
    "ToolRateLimit",
    "ToolSpec",
    "ToolRegistry",
]
