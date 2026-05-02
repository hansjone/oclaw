from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from .models import PLAN_MODE_NORMAL, PLAN_MODE_PLAN, PlanAgentStateV2
from .state_store import PlanAgentStateStoreV2


def _default_plan_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "plans"


def _resolve_plan_dir(store: Any) -> Path:
    raw = str(store.get_setting("AIA_EXPERT_PLAN_FILE_DIR") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (Path(__file__).resolve().parents[2] / p)
    return _default_plan_dir()


def _plan_template() -> str:
    return (
        "# Plan\n\n"
        "## Goal\n"
        "- \n\n"
        "## Scope\n"
        "- \n\n"
        "## Steps\n"
        "1. \n"
        "2. \n"
        "3. \n\n"
        "## Risks\n"
        "- \n\n"
        "## Acceptance\n"
        "- \n"
    )


class PlanModeManagerV2:
    def __init__(self, *, store: Any):
        self._store = store
        self._state_store = PlanAgentStateStoreV2(store)

    def load_state(self, *, session_id: str) -> PlanAgentStateV2:
        return self._state_store.load(session_id=session_id)

    def enter(
        self,
        *,
        session_id: str,
        owner_specialist: str,
        force_new_plan: bool = False,
    ) -> PlanAgentStateV2:
        prev = self._state_store.load(session_id=session_id)
        if prev.mode == PLAN_MODE_PLAN and not force_new_plan:
            return prev
        sid = str(session_id or "").strip()
        if not sid:
            return prev
        plan_id = uuid.uuid4().hex
        plan_root = _resolve_plan_dir(self._store) / sid
        plan_root.mkdir(parents=True, exist_ok=True)
        plan_path = plan_root / f"{plan_id}.md"
        plan_content = _plan_template()
        plan_path.write_text(plan_content, encoding="utf-8")
        now_ms = int(time.time() * 1000)
        next_state = PlanAgentStateV2(
            mode=PLAN_MODE_PLAN,
            owner_specialist=str(owner_specialist or "generalist").strip().lower() or "generalist",
            plan_id=plan_id,
            plan_path=str(plan_path),
            plan_content=plan_content,
            plan_confirmed=False,
            entered_at_ms=now_ms,
            updated_at_ms=now_ms,
            last_user_text_norm="",
            plan_loop_count=0,
        )
        return self._state_store.save(session_id=sid, state=next_state)

    def refresh_plan_content(self, *, session_id: str) -> PlanAgentStateV2:
        st = self._state_store.load(session_id=session_id)
        p = Path(str(st.plan_path or "").strip())
        if not p.exists() or not p.is_file():
            return st
        content = p.read_text(encoding="utf-8", errors="replace")
        return self._state_store.save(
            session_id=session_id,
            state=PlanAgentStateV2(
                mode=st.mode,
                owner_specialist=st.owner_specialist,
                plan_id=st.plan_id,
                plan_path=st.plan_path,
                plan_content=content,
                plan_confirmed=st.plan_confirmed,
                entered_at_ms=st.entered_at_ms,
                updated_at_ms=st.updated_at_ms,
                last_user_text_norm=st.last_user_text_norm,
                plan_loop_count=st.plan_loop_count,
            ),
        )

    def update_loop_guard(self, *, session_id: str, user_text_norm: str) -> PlanAgentStateV2:
        st = self._state_store.load(session_id=session_id)
        nxt_count = int(st.plan_loop_count or 0) + 1 if user_text_norm and user_text_norm == st.last_user_text_norm else 0
        return self._state_store.save(
            session_id=session_id,
            state=PlanAgentStateV2(
                mode=st.mode,
                owner_specialist=st.owner_specialist,
                plan_id=st.plan_id,
                plan_path=st.plan_path,
                plan_content=st.plan_content,
                plan_confirmed=st.plan_confirmed,
                entered_at_ms=st.entered_at_ms,
                updated_at_ms=st.updated_at_ms,
                last_user_text_norm=user_text_norm,
                plan_loop_count=nxt_count,
            ),
        )

    def confirm(self, *, session_id: str) -> PlanAgentStateV2:
        st = self.refresh_plan_content(session_id=session_id)
        return self._state_store.save(
            session_id=session_id,
            state=PlanAgentStateV2(
                mode=PLAN_MODE_NORMAL,
                owner_specialist=st.owner_specialist,
                plan_id=st.plan_id,
                plan_path=st.plan_path,
                plan_content=st.plan_content,
                plan_confirmed=True,
                entered_at_ms=st.entered_at_ms,
                updated_at_ms=st.updated_at_ms,
                last_user_text_norm="",
                plan_loop_count=0,
            ),
        )

    def build_approved_execution_message(self, *, state: PlanAgentStateV2, lang: str) -> str:
        is_en = str(lang or "").startswith("en")
        plan_path = str(state.plan_path or "").strip() or "unknown"
        plan_content = str(state.plan_content or "").strip()
        if plan_content:
            if is_en:
                return (
                    "User has approved your plan. You can now start implementation.\n\n"
                    f"Plan file: {plan_path}\n\n"
                    f"## Approved Plan\n{plan_content}"
                )
            return (
                "用户已确认计划，你可以开始执行实现。\n\n"
                f"计划文件：{plan_path}\n\n"
                f"## 已确认计划\n{plan_content}"
            )
        return (
            f"Plan approved. You can now start implementation. Plan file: {plan_path}"
            if is_en
            else f"计划已确认，你可以开始执行实现。计划文件：{plan_path}"
        )

    def exit_without_confirm(self, *, session_id: str) -> PlanAgentStateV2:
        st = self._state_store.load(session_id=session_id)
        return self._state_store.save(
            session_id=session_id,
            state=PlanAgentStateV2(
                mode=PLAN_MODE_NORMAL,
                owner_specialist=st.owner_specialist,
                plan_id=st.plan_id,
                plan_path=st.plan_path,
                plan_content=st.plan_content,
                plan_confirmed=False,
                entered_at_ms=st.entered_at_ms,
                updated_at_ms=st.updated_at_ms,
                last_user_text_norm="",
                plan_loop_count=0,
            ),
        )


__all__ = ["PlanModeManagerV2"]

