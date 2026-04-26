from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TaskKind = str
RiskLevel = str


@dataclass(frozen=True)
class AgentTask:
    session_id: str
    user_text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    kind: TaskKind = "generalist"
    risk_level: RiskLevel = "low"
    specialist: str = "generalist"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingDecision:
    kind: TaskKind
    specialist: str
    risk_level: RiskLevel
    reason: str


# 规范说明：
# - specialist: 路由/计划层使用的专家标识（例如 ops / generalist）
# - expert: 工具目录名（例如 network_ops / generalist）
# - tool_tags: 运行期开关过滤（例如 ops / system）


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    specialist: str
    objective: str
    input_text: str
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ManagerPlan:
    plan_id: str
    strategy: str
    steps: list[PlanStep] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True)
class SpecialistToolTrace:
    """单条工具调用摘要（专家会话内执行，用于交付给全能者的可追溯信息）。"""

    name: str
    ok: bool
    latency_ms: int = 0


@dataclass(frozen=True)
class SpecialistDelivery:
    """
    专家 → 全能者（Core）的结构化交付。

    - answer_text：面向用户的专家结论（已结合工具结果，与 output_text 对齐）。
    - tool_traces：本步内在专家侧实际执行的工具摘要（非全能者直接执行）。
    """

    version: int = 1
    specialist: str = ""
    step_id: str = ""
    answer_text: str = ""
    tool_traces: tuple[SpecialistToolTrace, ...] = ()
    notes: str = ""


def format_specialist_handoff_for_core(res: "SpecialistResult") -> str:
    """将专家结果格式化为全能者合并提示中的单步条目（可读 + 明示 handoff 边界）。"""
    if res.delivery and res.delivery.answer_text.strip():
        d = res.delivery
        lines = [
            f"### handoff v{d.version} step={d.step_id} specialist={d.specialist}",
            "role=specialist_completed",
            f"answer_for_user:\n{d.answer_text.strip()}",
        ]
        if d.tool_traces:
            parts = []
            for t in d.tool_traces:
                parts.append(f"{t.name}(ok={t.ok}, {t.latency_ms}ms)")
            lines.append(f"tools_executed_inside_specialist: " + "; ".join(parts))
        else:
            lines.append("tools_executed_inside_specialist: (none)")
        if (d.notes or "").strip():
            lines.append(f"notes: {d.notes.strip()}")
        lines.append(
            "instruction_for_core: 专家已基于工具输出整理 answer_for_user；请仅做合并、润色与一致性检查，勿编造与工具矛盾的事实。"
        )
        return "\n".join(lines)
    return f"[{res.specialist}/{res.step_id}] {res.output_text}"


@dataclass(frozen=True)
class SpecialistResult:
    step_id: str
    specialist: str
    success: bool
    output_text: str
    latency_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)
    delivery: SpecialistDelivery | None = None


@dataclass(frozen=True)
class FinalDecision:
    plan_id: str
    summary: str
    confidence: float
    references: list[str] = field(default_factory=list)
