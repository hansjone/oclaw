"""Transcript replay policy for OpenAI-compatible Chat Completions.

Inspired by Oclaw (MIT) `src/agents/transcript-policy.ts` defaults for
`openai-completions`: enable strict tool-call-id sanitization so proxies and
multi-provider histories do not break on id format / length.

See OCLAW_MIT_LICENSE.txt in this package.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from oclaw.platform.llm.tool_call_id import DEFAULT_MAX_OPENAI_TOOL_CALL_ID_LEN


@dataclass(frozen=True)
class ReplayPolicy:
    """Controls pre-request normalization of chat messages for tool-use flow."""

    enabled: bool
    sanitize_tool_call_ids: bool
    repair_tool_pairing: bool
    max_tool_call_id_len: int


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return default


def resolve_replay_policy(
    base_url: str | None,
    model_id: str | None,
    *,
    llm_profile_mode: str | None = None,
) -> ReplayPolicy:
    """Resolve replay policy for OpenAI-compatible chat completions.

    When enabled (default): sanitize assistant/tool ids before every request.
    This matches oclaw's strict OpenAI-compatible replay defaults.
    """
    del base_url, model_id, llm_profile_mode  # reserved for provider-specific overrides

    if not _env_bool("AIA_REPLAY_POLICY_ENABLED", True):
        return ReplayPolicy(
            enabled=False,
            sanitize_tool_call_ids=False,
            repair_tool_pairing=False,
            max_tool_call_id_len=DEFAULT_MAX_OPENAI_TOOL_CALL_ID_LEN,
        )

    max_len = DEFAULT_MAX_OPENAI_TOOL_CALL_ID_LEN
    raw_ml = str(os.getenv("AIA_TOOL_CALL_ID_MAX_LEN") or "").strip()
    if raw_ml.isdigit():
        max_len = max(8, min(int(raw_ml), 128))

    repair = _env_bool("AIA_REPLAY_REPAIR_TOOL_PAIRING", True)

    return ReplayPolicy(
        enabled=True,
        sanitize_tool_call_ids=True,
        repair_tool_pairing=repair,
        max_tool_call_id_len=max_len,
    )


def apply_replay_policy_to_messages(
    messages: list[dict[str, Any]],
    policy: ReplayPolicy,
) -> list[dict[str, Any]]:
    """Apply repair + id sanitization in order."""
    if not policy.enabled or not messages:
        return messages
    from oclaw.platform.llm.tool_call_id import (
        repair_orphan_tool_messages,
        rewrite_openai_chat_messages_tool_ids,
    )

    out = messages
    if policy.repair_tool_pairing:
        out = repair_orphan_tool_messages(out)
    if policy.sanitize_tool_call_ids:
        out = rewrite_openai_chat_messages_tool_ids(out, max_len=policy.max_tool_call_id_len)
    return out
