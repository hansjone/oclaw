from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    needs_confirmation: bool
    reason: str
    confirm_token: str | None = None
    redactions: dict[str, str] | None = None


@dataclass(frozen=True)
class ToolPolicyContext:
    session_id: str
    user_text: str
    specialist: str = ""
    task_kind: str = ""


@dataclass(frozen=True)
class ActionPolicyContext:
    session_id: str
    tenant_id: str = ""
    user_id: str = ""
    channel: str = ""
    user_text: str = ""
    action: str = ""
    target: dict[str, Any] | None = None


class PolicyEngine:
    _HIGH_RISK_TOOLS = {"port_scan", "run_command", "write_file", "apply_patch", "git_commit", "git_push"}
    _HIGH_RISK_ACTIONS = {"send_broadcast", "send_mention_all", "home_control", "payment_transfer"}

    def is_high_risk_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        name = (tool_name or "").strip()
        if not name:
            return False
        if name in self._HIGH_RISK_TOOLS:
            return True
        blob = f"{name}\n{arguments or {}}".lower()
        return any(k in blob for k in ("delete", "remove", "rm ", "drop", "reset", "format", "shutdown", "reboot"))

    def new_confirmation_token(self) -> str:
        return secrets.token_urlsafe(8)

    def decide_tool(self, *, tool_name: str, arguments: dict[str, Any], ctx: ToolPolicyContext) -> PolicyDecision:
        if self.is_high_risk_tool(tool_name, arguments):
            return PolicyDecision(allowed=True, needs_confirmation=True, reason="high_risk_tool_requires_confirmation")
        return PolicyDecision(allowed=True, needs_confirmation=False, reason="allowed")

    def decide_action(self, *, ctx: ActionPolicyContext) -> PolicyDecision:
        action = (ctx.action or "").strip().lower()
        if not action:
            return PolicyDecision(allowed=True, needs_confirmation=False, reason="allowed")
        if action in self._HIGH_RISK_ACTIONS:
            return PolicyDecision(allowed=True, needs_confirmation=True, reason=f"high_risk_action:{action}")
        target = ctx.target or {}
        if action in {"send_message", "send"}:
            if bool(target.get("mention_all")):
                return PolicyDecision(allowed=True, needs_confirmation=True, reason="high_risk_action:mention_all")
            if bool(target.get("is_group")) and int(target.get("member_count") or 0) >= 50:
                return PolicyDecision(allowed=True, needs_confirmation=True, reason="high_risk_action:large_group")
        return PolicyDecision(allowed=True, needs_confirmation=False, reason="allowed")


__all__ = ["PolicyDecision", "ToolPolicyContext", "ActionPolicyContext", "PolicyEngine"]
