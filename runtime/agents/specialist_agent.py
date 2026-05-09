from __future__ import annotations

import json
import os
import sys
import time
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from oclaw.runtime.chat.agent import Agent
from oclaw.runtime.chat.agent import GenerationInterrupted
from oclaw.runtime.agents.network_ops_agent import NetworkOpsAgent
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.platform.llm.image_legacy_client import (
    IMAGE_SPECIALIST_DEFAULT_PROMPT_ZH,
    collect_legacy_lane_images_from_attachments,
    legacy_image_assistant_body_with_placeholder,
    legacy_image_turn_bundle,
    send_legacy_image_messages,
)
from oclaw.runtime.tools import default_registry
from oclaw.runtime.agents.specialists import expert_name_for_specialist

from oclaw.runtime.chat.turn_types import TurnRunOutcome
from oclaw.runtime.relay_pointer import build_manifest_from_attachment_refs
from oclaw.runtime.types import RelayShareEnvelope
from oclaw.runtime.orchestration.protocol import (
    AgentTask,
    PlanStep,
    SpecialistDelivery,
    SpecialistResult,
    SpecialistToolTrace,
)


@dataclass(frozen=True)
class SpecialistProfile:
    name: str
    system_prefix: str
    tool_tags: frozenset[str] | None = None


@dataclass
class SpecialistAgentRunner:
    store: SqliteStore
    model: Any
    llm_profile_mode: str | None
    lang: str
    profiles: dict[str, SpecialistProfile] = field(default_factory=dict)
    model_by_specialist: dict[str, Any] = field(default_factory=dict)
    llm_mode_by_specialist: dict[str, str | None] = field(default_factory=dict)
    _agent_cache: dict[tuple, Agent] = field(default_factory=dict, init=False, repr=False)

    @staticmethod
    def _allowlist_mutation_fingerprint(
        store: SqliteStore,
        *,
        policy_session_id: str | None = None,
        path_policy_tenant_id: str | None = None,
        path_policy_user_id: str | None = None,
    ) -> str:
        t = (path_policy_tenant_id or "").strip() or None
        u = (path_policy_user_id or "").strip() or None
        if (not t or not u) and (policy_session_id or "").strip():
            try:
                own = store.get_ui_session_owner(session_id=str(policy_session_id).strip()) or {}
            except Exception:
                own = {}
            t = t or (str(own.get("tenant_id") or "").strip() or None)
            u = u or (str(own.get("user_id") or "").strip() or None)
        if not t or not u:
            return "0"
        try:
            row = store.get_user_workspace_path_allowlist(tenant_id=t, user_id=u)
        except Exception:
            row = None
        if not row or not isinstance(row, dict):
            return "0|"
        er = str(row.get("extra_roots") or "")
        return f"{1 if int(row.get('allow_any_path') or 0) else 0}|{str(row.get('updated_at') or '')}|{er[:2000]}"

    def _agent_cache_fingerprint(
        self,
        specialist: str,
        prof: SpecialistProfile,
        *,
        policy_session_id: str | None = None,
        path_policy_tenant_id: str | None = None,
        path_policy_user_id: str | None = None,
    ) -> str:
        tool_names: list[str] = []
        try:
            regs = default_registry(
                expert=expert_name_for_specialist(prof.name),
                specialist=prof.name,
                policy_session_id=policy_session_id,
                path_policy_tenant_id=path_policy_tenant_id,
                path_policy_user_id=path_policy_user_id,
                store=self.store,
            )
            tool_names = sorted([str(t.name) for t in regs.list()])
        except Exception:
            tool_names = []
        raw = json.dumps(
            {
                "specialist": specialist,
                "profile_name": prof.name,
                "system_prefix": prof.system_prefix,
                "tool_names": tool_names,
                "tool_tags": sorted(list(prof.tool_tags or frozenset())),
                "policy_session_tail": (str(policy_session_id or "")[-16:]),
                "allowlist_fp": self._allowlist_mutation_fingerprint(
                    self.store,
                    policy_session_id=policy_session_id,
                    path_policy_tenant_id=path_policy_tenant_id,
                    path_policy_user_id=path_policy_user_id,
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _resolve_profile_and_model(self, specialist: str) -> tuple[SpecialistProfile, Any, str | None]:
        prof = self.profiles.get(specialist) or self.profiles["generalist"]
        chosen_model = self.model_by_specialist.get(prof.name) or self.model
        chosen_mode = self.llm_mode_by_specialist.get(prof.name) or self.llm_profile_mode
        return prof, chosen_model, chosen_mode

    def _build_agent_for(
        self,
        specialist: str,
        *,
        policy_session_id: str | None = None,
        use_cache: bool = True,
        path_policy_tenant_id: str | None = None,
        path_policy_user_id: str | None = None,
    ) -> Agent:
        prof, chosen_model, chosen_mode = self._resolve_profile_and_model(specialist)
        cache_fp = self._agent_cache_fingerprint(
            specialist,
            prof,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
        )
        alfp = self._allowlist_mutation_fingerprint(
            self.store,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
        )
        cache_key = (prof.name, id(chosen_model), chosen_mode, self.lang, cache_fp, str(policy_session_id or ""), alfp)
        if use_cache:
            cached = self._agent_cache.get(cache_key)
            if cached is not None:
                return cached
        if prof.name == "ops":
            agent: Agent = NetworkOpsAgent(
                store=self.store,
                model=chosen_model,
                lang=self.lang,
                llm_profile_mode=chosen_mode,
                system_prompt=prof.system_prefix,
                policy_session_id=policy_session_id,
                path_policy_tenant_id=path_policy_tenant_id,
                path_policy_user_id=path_policy_user_id,
            )
            if use_cache:
                self._agent_cache[cache_key] = agent
            return agent
        tools = default_registry(
            expert=expert_name_for_specialist(prof.name),
            specialist=prof.name,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            store=self.store,
        )
        agent = Agent(
            store=self.store,
            tools=tools,
            model=chosen_model,
            system_prompt=prof.system_prefix,
            lang=self.lang,
            llm_profile_mode=chosen_mode,
        )
        if use_cache:
            self._agent_cache[cache_key] = agent
        return agent

    def run_specialist(
        self,
        *,
        parent_task: AgentTask,
        step: PlanStep,
        session_id: str | None = None,
        use_cache: bool = True,
        on_progress: Optional[Callable[[str], None]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> SpecialistResult:
        started = time.perf_counter()
        if on_progress:
            obj = (step.objective or "").strip().replace("\n", " ")
            if len(obj) > 140:
                obj = obj[:137] + "..."
            on_progress(f"[sp.start] {step.step_id} specialist={step.specialist} objective={obj}")
        created_session_id: str | None = None
        if not session_id:
            temp_session = self.store.create_session(f"specialist:{step.specialist}")
            session_id = temp_session.id
            created_session_id = session_id
        # User chat session for workspace/MCP path policy (specialist temp session usually has no ui_session_owner).
        _raw_policy_sid = str(parent_task.session_id or "").strip() or str(session_id or "").strip()
        policy_session_id: str | None = _raw_policy_sid if _raw_policy_sid else None
        _meta: dict[str, Any] = parent_task.metadata if isinstance(getattr(parent_task, "metadata", None), dict) else {}
        _path_tenant = str(_meta.get("tenant_id") or "").strip() or None
        _path_user = str(_meta.get("user_id") or "").strip() or None
        prompt = (
            f"Specialist: {step.specialist}\n"
            f"Objective: {step.objective}\n"
            f"Parent user request: {parent_task.user_text}\n"
            f"Step input: {step.input_text}\n"
            "Execution policy: when the user asks to read/open/list/summarize concrete files, URLs, or MCP resources, "
            "execute with available tools first. Do not return generic optimization plans unless explicitly requested.\n"
        )
        image_input_count = 0
        image_input_kind: list[str] = []
        image_protocol = ""
        image_debug_schema = ""
        image_debug_payload: dict[str, Any] | str = {}
        specialist_delivery: SpecialistDelivery | None = None
        try:
            if step.specialist == "image":
                image_protocol = "messages.content.image"
                selected_images = collect_legacy_lane_images_from_attachments(
                    list(parent_task.attachments or []),
                    max_images=3,
                )
                image_input_count = len(selected_images)
                image_input_kind = ["data_url" if s.startswith("data:") else "url" for s in selected_images]
                if not selected_images:
                    output = "Image specialist received no image input."
                    ok = False
                else:
                    # Use the user's chosen model/session profile (same as specialist routing UI). Wrong model ⇒ upstream HTTP error as-is (no OCR lane, no alternate payload).
                    _, chosen_model, _ = self._resolve_profile_and_model(step.specialist)
                    text_parts = [
                        str(x).strip()
                        for x in (step.objective, step.input_text, parent_task.user_text)
                        if str(x or "").strip()
                    ]
                    user_text = "\n".join(text_parts) if text_parts else IMAGE_SPECIALIST_DEFAULT_PROMPT_ZH
                    if str(os.getenv("AIA_IMAGE_EXPERT_DEBUG_PRINT_PAYLOAD") or "").strip().lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    ):
                        try:
                            sys.stderr.write(
                                "[oclaw specialist:image] lane=legacy_http → send_legacy_image_messages "
                                "(NOT OpenAIResponsesModel).\n"
                            )
                            sys.stderr.flush()
                        except Exception:
                            pass
                    resp = send_legacy_image_messages(
                        images=selected_images,
                        prompt=user_text,
                        model=str(getattr(chosen_model, "model", "") or "").strip() or None,
                        api_key=str(getattr(chosen_model, "api_key", "") or "").strip() or None,
                        base_url=str(getattr(chosen_model, "base_url", "") or "").strip() or None,
                    )
                    image_debug_schema = str(resp.get("debug_used_schema") or "").strip()
                    dbg = resp.get("debug_used_debug")
                    if isinstance(dbg, dict):
                        image_debug_payload = dbg
                    elif dbg is not None:
                        image_debug_payload = str(dbg)
                    ok, output, produced_attachments = legacy_image_turn_bundle(resp)
                    output = legacy_image_assistant_body_with_placeholder(
                        lang=self.lang,
                        body_text=output,
                        produced=produced_attachments if ok else None,
                    )
                    self.store.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=output,
                        attachments=produced_attachments or None,
                    )
                specialist_delivery = SpecialistDelivery(
                    specialist=step.specialist,
                    step_id=step.step_id,
                    answer_text=str(output or ""),
                    tool_traces=(),
                    notes="image_pipeline",
                )
            else:
                agent = self._build_agent_for(
                    step.specialist,
                    policy_session_id=policy_session_id,
                    use_cache=use_cache,
                    path_policy_tenant_id=_path_tenant,
                    path_policy_user_id=_path_user,
                )
                from oclaw.runtime.gateway import OclawGateway
                from oclaw.runtime.types import StandardMessage

                gw = OclawGateway(store=self.store)
                msg = StandardMessage(
                    session_id=str(session_id),
                    tenant_id=str(_path_tenant or ""),
                    user_id=str(_path_user or ""),
                    role="member",
                    channel="specialist",
                    text=str(prompt or ""),
                    attachments=list(parent_task.attachments or []),
                    metadata={
                        "tenant_id": str(_path_tenant or ""),
                        "user_id": str(_path_user or ""),
                        "channel": f"specialist:{step.specialist}",
                    },
                )
                output = gw.handle_turn(
                    msg=msg,
                    lang=str(getattr(agent, "lang", "zh") or "zh"),
                    executor=agent,
                    on_token=on_token,
                    on_progress=on_progress,
                    on_tool_ui=on_tool_ui,
                    should_stop=should_stop,
                ).reply_text
                ok = bool((output or "").strip())
                outcome = getattr(agent, "_last_turn_outcome", None)
                if isinstance(outcome, TurnRunOutcome):
                    traces = tuple(
                        SpecialistToolTrace(
                            name=str(x.get("name") or ""),
                            ok=bool(x.get("ok")),
                            latency_ms=int(x.get("latency_ms") or x.get("duration_ms") or 0),
                        )
                        for x in outcome.tool_traces
                    )
                    specialist_delivery = SpecialistDelivery(
                        specialist=step.specialist,
                        step_id=step.step_id,
                        answer_text=str(output or ""),
                        tool_traces=traces,
                        notes=str(outcome.handoff_note or ""),
                    )
        except GenerationInterrupted:
            raise
        except Exception as e:
            output = f"{type(e).__name__}: {e}"
            ok = False
        finally:
            produced_attachments: list[dict[str, Any]] = []
            try:
                rows = self.store.get_messages(session_id=session_id, limit=40) if session_id else []
                for m in reversed(rows):
                    if str(m.role) != "assistant":
                        continue
                    if not m.attachments:
                        continue
                    raw = json.loads(m.attachments)
                    if isinstance(raw, list):
                        produced_attachments = [a for a in raw if isinstance(a, dict)]
                    break
            except Exception:
                produced_attachments = []
            if created_session_id:
                try:
                    parent_sid = str(parent_task.session_id or "").strip()
                    if parent_sid and parent_sid != str(created_session_id):
                        # Preserve tool usage telemetry: tool uses run inside temp specialist sessions.
                        # If we delete temp sessions directly, FK cascade would drop those tool_log rows.
                        self.store.move_tool_logs_to_session(
                            from_session_id=str(created_session_id),
                            to_session_id=parent_sid,
                        )
                except Exception:
                    pass
                self.store.delete_session(created_session_id)
        latency = int((time.perf_counter() - started) * 1000)
        if on_progress:
            on_progress(
                f"[sp.done] {step.step_id} specialist={step.specialist} ok={ok} latency_ms={latency}"
            )
        scope_id = str(session_id or parent_task.session_id or "").strip()
        manifest = build_manifest_from_attachment_refs(
            produced_attachments,
            scope_id=scope_id,
            source_agent=str(step.specialist or ""),
            ttl_policy="turn",
        )
        relay_env = RelayShareEnvelope(
            schema_version="v1",
            trace_id=str((parent_task.metadata or {}).get("trace_id") or ""),
            run_id=str((parent_task.metadata or {}).get("run_id") or ""),
            attempt_no=int((parent_task.metadata or {}).get("attempt_no") or 0),
            attachments=manifest,
        )
        return SpecialistResult(
            step_id=step.step_id,
            specialist=step.specialist,
            success=ok,
            output_text=output,
            latency_ms=latency,
            metadata={
                "objective": step.objective,
                "attachments": produced_attachments,
                "relay_share_envelope": relay_env.to_dict(),
                "image_input_count": image_input_count,
                "image_input_kind": image_input_kind,
                "image_protocol": image_protocol,
                "image_debug_schema": image_debug_schema,
                "image_debug_payload": image_debug_payload,
            },
            delivery=specialist_delivery,
        )
