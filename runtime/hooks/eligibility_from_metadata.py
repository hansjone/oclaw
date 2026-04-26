from __future__ import annotations

from typing import Any

from .hook_types import HookEligibilityContext, HookRemoteEligibility


def hook_eligibility_from_message_metadata(metadata: dict[str, Any] | None) -> HookEligibilityContext | None:
    """
    Build ``HookEligibilityContext`` from inbound message metadata (e.g. gateway / API).

    Expected shape (JSON-friendly):

    .. code-block:: json

        {
          "hookEligibility": {
            "remote": {
              "platforms": ["darwin", "linux", "windows"],
              "binsPresent": ["git", "node"],
              "note": "from remote agent / bridge"
            }
          }
        }

    - ``platforms``: when non-empty, overrides hook ``metadata.oclaw.os`` for eligibility (same as TS).
    - ``binsPresent``: when non-empty, supplies ``hasBin`` / ``hasAnyBin`` predicates so bin checks
      can reflect a **remote** execution environment instead of ``shutil.which`` on this machine.
    """
    if not isinstance(metadata, dict):
        return None
    block = metadata.get("hookEligibility")
    if not isinstance(block, dict):
        return None
    rem = block.get("remote")
    if not isinstance(rem, dict):
        return None

    platforms_raw = rem.get("platforms")
    platforms: list[str] = []
    if isinstance(platforms_raw, list):
        platforms = [str(x).strip().lower() for x in platforms_raw if str(x or "").strip()]

    bins_raw = rem.get("binsPresent")
    bins_present: set[str] = set()
    if isinstance(bins_raw, list):
        bins_present = {str(x).strip() for x in bins_raw if str(x or "").strip()}

    note_raw = rem.get("note")
    note = str(note_raw).strip() if isinstance(note_raw, str) else ""

    if not platforms and not bins_present and not note:
        return None

    r: HookRemoteEligibility = {}
    if platforms:
        r["platforms"] = platforms
    if note:
        r["note"] = note

    if bins_present:

        def has_bin(name: str) -> bool:
            return str(name or "").strip() in bins_present

        def has_any_bin(names: list[Any]) -> bool:
            return any(has_bin(str(x or "")) for x in (names or []))

        r["hasBin"] = has_bin
        r["hasAnyBin"] = has_any_bin

    return {"remote": r}
