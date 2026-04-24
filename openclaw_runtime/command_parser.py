from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandAction = Literal["new", "reset"]


@dataclass(frozen=True)
class ParsedCommand:
    action: CommandAction
    raw: str
    command: str
    args: tuple[str, ...]


def parse_internal_command(text: str) -> ParsedCommand | None:
    """
    Parse top-level slash/plain reset commands.

    Supported:
    - /new, new
    - /reset, reset
    """
    t = str(text or "").strip()
    if not t:
        return None
    parts = [x for x in t.split() if str(x or "").strip()]
    if not parts:
        return None
    first_raw = parts[0].strip()
    first_norm = first_raw.lower()
    if first_norm.startswith(("/", "／")):
        first_norm = first_norm[1:]
    # English aliases + localized aliases
    new_aliases = {"new", "n", "新建", "重开"}
    reset_aliases = {"reset", "r", "重置", "清空"}
    if first_norm in new_aliases:
        return ParsedCommand(action="new", raw=t, command=first_norm, args=tuple(parts[1:]))
    if first_norm in reset_aliases:
        return ParsedCommand(action="reset", raw=t, command=first_norm, args=tuple(parts[1:]))
    return None


__all__ = ["ParsedCommand", "parse_internal_command"]

