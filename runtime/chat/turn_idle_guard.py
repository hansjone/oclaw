"""Turn-local idle / checklist guard to cut narration-only and no-progress loops."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal


IdleAction = Literal["continue", "nudge", "early_finalize"]


def _env_int(name: str, default: int, *, min_v: int = 1, max_v: int = 20) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        n = int(raw)
    except Exception:
        return default
    return max(min_v, min(int(n), max_v))


def idle_guard_enabled() -> bool:
    raw = str(os.getenv("AIA_TURN_IDLE_GUARD") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


@dataclass
class RoundStats:
    round_idx: int
    had_tool_calls: bool
    ok_count: int = 0
    fail_count: int = 0
    schema_fail_count: int = 0
    retry_guard_count: int = 0
    tool_names: list[str] = field(default_factory=list)


@dataclass
class IdleGuardDecision:
    action: IdleAction
    reason: str
    nudge_text: str = ""


@dataclass
class TurnIdleTracker:
    """Tracks per-turn progress and decides nudge / early finalize."""

    lang: str = "en"
    short_intent: str | None = None
    max_idle_rounds: int = field(default_factory=lambda: _env_int("AIA_TURN_IDLE_MAX_ROUNDS", 2))
    max_schema_fails: int = field(default_factory=lambda: _env_int("AIA_TURN_IDLE_MAX_SCHEMA_FAILS", 3))
    rounds: list[RoundStats] = field(default_factory=list)
    nudged: bool = False
    total_ok: int = 0
    total_schema_fails: int = 0

    def record_from_traces(
        self,
        *,
        round_idx: int,
        had_tool_calls: bool,
        round_traces: list[dict[str, Any]],
        results_by_id: dict[str, tuple[dict[str, Any], int]] | None = None,
    ) -> RoundStats:
        ok = 0
        fail = 0
        schema = 0
        guard = 0
        names: list[str] = []
        # Prefer live results when available (richer failure_class).
        payloads: list[dict[str, Any]] = []
        if results_by_id:
            for _cid, (payload, _dur) in results_by_id.items():
                if isinstance(payload, dict):
                    payloads.append(payload)
        for tr in round_traces or []:
            name = str((tr or {}).get("name") or "").strip()
            if name:
                names.append(name)
            if not payloads:
                if (tr or {}).get("ok") is True:
                    ok += 1
                elif (tr or {}).get("ok") is False:
                    fail += 1
        for payload in payloads:
            if payload.get("ok") is True:
                ok += 1
                continue
            fail += 1
            klass = str(payload.get("failure_class") or payload.get("error_class") or "").lower()
            code = str(payload.get("error_code") or "").lower()
            if klass == "schema_validation" or code in {"tool_invalid_arguments", "invalid_arguments"}:
                schema += 1
            if klass == "retry_guard" or code in {
                "identical_retry_blocked",
                "retry_forbidden_blocked",
                "tool_loop_guard",
                "cli_call_budget_exceeded",
                "cli_fail_budget_exceeded",
            }:
                guard += 1
        stats = RoundStats(
            round_idx=int(round_idx),
            had_tool_calls=bool(had_tool_calls),
            ok_count=int(ok),
            fail_count=int(fail),
            schema_fail_count=int(schema),
            retry_guard_count=int(guard),
            tool_names=names,
        )
        self.rounds.append(stats)
        self.total_ok += int(ok)
        self.total_schema_fails += int(schema)
        return stats

    def decide_after_assistant_no_tools(self) -> IdleGuardDecision:
        """Model returned text without tool_calls."""
        if not idle_guard_enabled():
            return IdleGuardDecision(action="continue", reason="disabled")
        # Short-intent recipes require an evidence tool before answering.
        intent = str(self.short_intent or "").strip()
        if intent and intent != "continue" and self.total_ok == 0 and not self.nudged:
            self.nudged = True
            return IdleGuardDecision(
                action="nudge",
                reason="short_intent_narration_only",
                nudge_text=self._nudge_text(reason="narration_only"),
            )
        return IdleGuardDecision(action="continue", reason="allow_text_reply")

    def decide_after_tools(self, stats: RoundStats) -> IdleGuardDecision:
        if not idle_guard_enabled():
            return IdleGuardDecision(action="continue", reason="disabled")

        if self.total_schema_fails >= int(self.max_schema_fails) and self.total_ok == 0:
            return IdleGuardDecision(
                action="early_finalize",
                reason="schema_fail_budget",
                nudge_text=self._nudge_text(reason="schema_fail_budget"),
            )

        # Count trailing idle rounds: tools ran but zero successes.
        idle_streak = 0
        for r in reversed(self.rounds):
            if r.had_tool_calls and r.ok_count == 0:
                idle_streak += 1
                continue
            break

        if idle_streak >= int(self.max_idle_rounds) and self.total_ok == 0:
            return IdleGuardDecision(
                action="early_finalize",
                reason="idle_no_progress",
                nudge_text=self._nudge_text(reason="idle_no_progress"),
            )

        # One soft nudge when a round is all retry_guard / schema with no success yet.
        if (
            stats.had_tool_calls
            and stats.ok_count == 0
            and (stats.schema_fail_count + stats.retry_guard_count) > 0
            and self.total_ok == 0
            and not self.nudged
        ):
            self.nudged = True
            return IdleGuardDecision(
                action="nudge",
                reason="round_no_progress",
                nudge_text=self._nudge_text(reason="round_no_progress"),
            )

        return IdleGuardDecision(action="continue", reason="progress_or_recoverable")

    def _nudge_text(self, *, reason: str) -> str:
        is_zh = str(self.lang or "").strip().lower().startswith("zh")
        intent = str(self.short_intent or "").strip()
        from runtime.tools.playbook_contracts import short_intent_first_step

        step = short_intent_first_step(intent)
        if is_zh:
            lines = ["[Idle guard] 本轮未取得有效工具证据，禁止空转。"]
            if step:
                tool, example = step
                lines.append(f"立即调用：{tool} 参数示例 {example}")
            elif reason == "schema_fail_budget":
                lines.append("参数多次不合法：按 tool 返回的 example/playbook 修正后只重试一次，然后直接作答。")
            else:
                lines.append("改参数或换 fallback 工具；若仍无证据则基于已知信息直接答复用户。")
            return "\n".join(lines)
        lines = ["[Idle guard] No usable tool evidence yet — stop spinning."]
        if step:
            tool, example = step
            lines.append(f"Call now: {tool} with example args {example}")
        elif reason == "schema_fail_budget":
            lines.append(
                "Repeated invalid arguments: fix once using the tool example/playbook, then answer."
            )
        else:
            lines.append("Change args or switch fallback tools; if still blocked, answer from what you have.")
        return "\n".join(lines)


__all__ = [
    "IdleGuardDecision",
    "RoundStats",
    "TurnIdleTracker",
    "idle_guard_enabled",
]
