from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnRunOutcome:
    final_text: str
    tool_traces: tuple[dict[str, Any], ...] = ()
    handoff_note: str = ""
    turn_uuid: str = ""


__all__ = ["TurnRunOutcome"]

