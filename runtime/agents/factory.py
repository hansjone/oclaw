"""根据存储与配置构建 Agent（不依赖 Streamlit）。"""

from __future__ import annotations

import os
from typing import Any

from oclaw.runtime.agents.agent_scope import resolve_default_agent_id
from oclaw.runtime.agents.network_ops_agent import NetworkOpsAgent
from oclaw.runtime.agents.specialist_agent import SpecialistProfile
from oclaw.runtime.agents.specialists import (
    AGENT_PROFILE_BINDINGS_KEY,
    normalize_specialist_id,
    agent_role_ids,
    MANAGER_AGENT_ID,
    specialist_ids,
    default_system_prefix_for_specialist,
    default_tool_tags_for_specialist,
    dump_agent_profile_bindings,
    expert_name_for_specialist,
    parse_agent_profile_bindings,
)
from oclaw.runtime.chat.agent import Agent
from oclaw.runtime.orchestration.inventory import inventory_snapshot
from oclaw.runtime.orchestration.memory import upsert_knowledge_chunks
from oclaw.platform.llm.chat_models import GoogleGeminiChatModel, OpenAIChatModel, RuleBasedChatModel, StaticTextChatModel
from oclaw.platform.llm.transports.anthropic_messages import AnthropicMessagesModel
from oclaw.platform.llm.transports.openai_responses import OpenAIResponsesModel
from oclaw.platform.persistence.sqlite_store import (
    SqliteStore,
    active_llm_profile_setting_key,
    agent_profile_bindings_setting_key,
    is_administrator_model_pool,
)
from oclaw.runtime.prompt_templates import render_prompt
from oclaw.runtime.tools.catalog import default_registry
from oclaw.runtime.tools.plugin_loader import sync_plugin_metadata


def _openai_missing_key_user_message(lang: str) -> str:
    prompt_id = "fallback/openai_missing_key_user.en.md" if (lang or "zh").startswith("en") else "fallback/openai_missing_key_user.zh.md"
    return render_prompt(prompt_id, strict=True)


DEFAULT_OLLAMA_BASE_URL = (
    (os.getenv("OLLAMA_BASE_URL") or os.getenv("OPENAI_BASE_URL_OLLAMA") or "").strip()
    or "http://127.0.0.1:11434/v1"
)
DEFAULT_OLLAMA_MODEL = (os.getenv("OLLAMA_MODEL") or "qwen2.5:7b").strip()
_OLLAMA_DUMMY_KEY = "ollama"


def _build_executor_components(
    store: SqliteStore,
    *,
    lang: str = "zh",
    profile_id: str | None = None,
    openai_api_key: str | None = None,
    llm_mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    viewer_user_id: str | None = None,
    viewer_username: str | None = None,
    viewer_tenant_id: str | None = None,
) -> tuple[
    NetworkOpsAgent,
    dict[str, SpecialistProfile],
    object,
    str,
    dict[str, object],
    dict[str, str],
]:
    lang = (lang or "zh").strip().lower()
    uid_scoped = str(viewer_user_id or "").strip()
    personal = bool(uid_scoped) and not is_administrator_model_pool(viewer_username)
    if personal:
        active_key = active_llm_profile_setting_key(uid_scoped, viewer_username)
        bindings_key = agent_profile_bindings_setting_key(uid_scoped, viewer_username)
        list_kw: dict[str, Any] = {"viewer_user_id": uid_scoped, "viewer_username": viewer_username}
        tid = str(viewer_tenant_id or "").strip()
        if tid:
            list_kw["viewer_tenant_id"] = tid
    else:
        active_key = "active_llm_profile_id"
        bindings_key = AGENT_PROFILE_BINDINGS_KEY
        list_kw = {}
    active_pid = (profile_id or store.get_setting(active_key) or "").strip()

    def _normalize_mode(raw: str | None) -> str:
        m = (raw or "").strip().lower()
        return m if m in ("openai", "openai_responses", "anthropic", "ollama", "rule", "google") else "rule"

    def _profile_thinking_config(profile: dict[str, Any] | None) -> tuple[bool, str]:
        if not isinstance(profile, dict):
            return False, ""
        think = bool(profile.get("thinking_mode_enabled"))
        eff = str(profile.get("reasoning_effort") or "").strip().lower()
        if eff not in ("", "low", "medium", "high"):
            eff = ""
        return think, eff

    def _apply_profile_thinking(model_obj: object, profile: dict[str, Any] | None) -> object:
        think, eff = _profile_thinking_config(profile)
        try:
            setattr(model_obj, "thinking_mode_enabled", think)
            setattr(model_obj, "reasoning_effort", eff)
        except Exception:
            pass
        return model_obj

    def _build_chat_model_for_profile(
        target_profile_id: str | None,
        *,
        allow_runtime_overrides: bool = False,
    ) -> tuple[object, str]:
        pid = (target_profile_id or "").strip()
        profile = store.get_llm_profile(pid) if pid else None
        mode = _normalize_mode(
            (llm_mode if allow_runtime_overrides else None)
            or (profile.get("mode") if profile else None)
            or os.getenv("AIA_ASSISTANT_MODE")
            or "openai"
        )

        raw_model = (model if allow_runtime_overrides else None) or (profile.get("model") if profile else None) or ""
        raw_model = str(raw_model).strip()
        if not raw_model:
            raw_model = (
                (os.getenv("OLLAMA_MODEL") or "").strip()
                if mode == "ollama"
                else (os.getenv("OPENAI_MODEL") or "").strip()
            )
        model_name = raw_model or (DEFAULT_OLLAMA_MODEL if mode == "ollama" else "gpt-4o-mini")

        bu = (base_url if allow_runtime_overrides else None) or (profile.get("base_url") if profile else None) or os.getenv("OPENAI_BASE_URL") or ""
        bu = str(bu).strip()
        stored_key = store.get_llm_profile_secret(pid) if pid else None
        api_key = (openai_api_key if allow_runtime_overrides else None) or stored_key or os.getenv("OPENAI_API_KEY")
        api_key = (api_key or "").strip()

        if mode == "openai_responses":
            if not api_key:
                return StaticTextChatModel(_openai_missing_key_user_message(lang)), mode
            return _apply_profile_thinking(OpenAIResponsesModel(model=model_name, api_key=api_key, base_url=bu or None), profile), mode
        if mode == "anthropic":
            akey = (
                (openai_api_key if allow_runtime_overrides else None)
                or stored_key
                or os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or ""
            )
            akey = str(akey or "").strip()
            if not akey:
                return StaticTextChatModel(_openai_missing_key_user_message(lang)), mode
            return AnthropicMessagesModel(model=model_name, api_key=akey, base_url=bu or None), mode
        if mode == "google":
            gkey = (
                (openai_api_key if allow_runtime_overrides else None)
                or stored_key
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or ""
            )
            gkey = str(gkey or "").strip()
            if not gkey:
                return StaticTextChatModel(_openai_missing_key_user_message(lang)), mode
            return GoogleGeminiChatModel(model=model_name, api_key=gkey, base_url=bu or None), mode

        if mode == "rule":
            return RuleBasedChatModel(), mode
        if mode == "ollama":
            ollama_base = (bu or DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL
            ollama_key = api_key or _OLLAMA_DUMMY_KEY
            return _apply_profile_thinking(OpenAIChatModel(model=model_name, api_key=ollama_key, base_url=ollama_base), profile), mode
        if not api_key:
            return StaticTextChatModel(_openai_missing_key_user_message(lang)), mode
        return _apply_profile_thinking(OpenAIChatModel(model=model_name, api_key=api_key, base_url=bu or None), profile), mode

    valid_profile_ids = {p["id"] for p in store.list_llm_profiles(visible_only=True, **list_kw)}
    if active_pid and active_pid not in valid_profile_ids:
        active_pid = ""
    active_model, active_mode = _build_chat_model_for_profile(active_pid, allow_runtime_overrides=True)

    raw_bindings = parse_agent_profile_bindings(store.get_setting(bindings_key))
    normalized_bindings: dict[str, str] = {}
    for rid in agent_role_ids():
        pid = (raw_bindings.get(rid) or "").strip()
        normalized_bindings[rid] = pid if pid in valid_profile_ids else ""
    if dump_agent_profile_bindings(normalized_bindings) != dump_agent_profile_bindings(raw_bindings):
        store.set_setting(bindings_key, dump_agent_profile_bindings(normalized_bindings))

    def _pick_model_for_role(role_id: str) -> tuple[object, str]:
        bound_pid = (normalized_bindings.get(role_id) or "").strip()
        if not bound_pid:
            return active_model, active_mode
        return _build_chat_model_for_profile(bound_pid, allow_runtime_overrides=False)

    manager_model, manager_mode = _pick_model_for_role(MANAGER_AGENT_ID)
    specialist_models: dict[str, object] = {}
    specialist_modes: dict[str, str] = {}
    for sid in specialist_ids():
        m, md = _pick_model_for_role(sid)
        specialist_models[sid] = m
        specialist_modes[sid] = md

    base_agent = NetworkOpsAgent(
        store=store,
        model=specialist_models.get("ops") or active_model,
        lang=lang,
        llm_profile_mode=specialist_modes.get("ops") or active_mode,
    )
    try:
        store.set_setting("agent_inventory_snapshot", str(inventory_snapshot()))
    except Exception:
        pass
    try:
        sync_plugin_metadata(store)
    except Exception:
        pass
    try:
        upsert_knowledge_chunks(
            store,
            source="builtin:src",
            chunks=[
                "Use tools for route lookup, path search, config diff, device ping, and log analysis.",
                "High-risk actions require explicit confirmation by user before execution.",
                "Prefer citing tool outputs and avoid fabricating external facts.",
            ],
        )
    except Exception:
        pass
    specialist_profiles = {
        sid: SpecialistProfile(
            name=sid,
            system_prefix=default_system_prefix_for_specialist(sid, lang),
            tool_tags=default_tool_tags_for_specialist(sid),
        )
        for sid in specialist_ids()
    }
    return (
        base_agent,
        specialist_profiles,
        manager_model,
        manager_mode,
        specialist_models,
        specialist_modes,
    )


def build_ops_agent(
    store: SqliteStore,
    *,
    lang: str = "zh",
    profile_id: str | None = None,
    openai_api_key: str | None = None,
    llm_mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    viewer_user_id: str | None = None,
    viewer_username: str | None = None,
    viewer_tenant_id: str | None = None,
) -> Any:
    del viewer_user_id, viewer_username, viewer_tenant_id
    return build_gateway_executor(
        store,
        lang=lang,
        specialist="ops",
        profile_id=profile_id,
        openai_api_key=openai_api_key,
        llm_mode=llm_mode,
        model=model,
        base_url=base_url,
    )


def build_gateway_executor(
    store: SqliteStore,
    *,
    lang: str = "zh",
    specialist: str | None = None,
    profile_id: str | None = None,
    openai_api_key: str | None = None,
    llm_mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    viewer_user_id: str | None = None,
    viewer_username: str | None = None,
    viewer_tenant_id: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> Any:
    base_agent, specialist_profiles, _, _, specialist_models, specialist_modes = _build_executor_components(
        store,
        lang=lang,
        profile_id=profile_id,
        openai_api_key=openai_api_key,
        llm_mode=llm_mode,
        model=model,
        base_url=base_url,
        viewer_user_id=viewer_user_id,
        viewer_username=viewer_username,
        viewer_tenant_id=viewer_tenant_id,
    )
    sid = normalize_specialist_id(specialist)
    if sid not in specialist_profiles:
        sid = "generalist"
    prof = specialist_profiles.get(sid) or specialist_profiles["generalist"]
    chosen_model = specialist_models.get(prof.name) or base_agent.model
    chosen_mode = specialist_modes.get(prof.name) or getattr(base_agent, "llm_profile_mode", None)
    if prof.name == "ops":
        return NetworkOpsAgent(
            store=store,
            model=chosen_model,
            lang=(lang or "zh").strip().lower(),
            llm_profile_mode=chosen_mode,
            system_prompt=prof.system_prefix,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
        )
    tools = default_registry(
        expert=expert_name_for_specialist(prof.name),
        specialist=prof.name,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
        store=store,
    )
    return Agent(
        store=store,
        tools=tools,
        model=chosen_model,
        system_prompt=prof.system_prefix,
        lang=(lang or "zh").strip().lower(),
        llm_profile_mode=chosen_mode,
    )


def build_gateway_executors(
    store: SqliteStore,
    *,
    lang: str = "zh",
    profile_id: str | None = None,
    openai_api_key: str | None = None,
    llm_mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    viewer_user_id: str | None = None,
    viewer_username: str | None = None,
    viewer_tenant_id: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> dict[str, Any]:
    manager = build_gateway_executor(
        store,
        lang=lang,
        specialist="generalist",
        profile_id=profile_id,
        openai_api_key=openai_api_key,
        llm_mode=llm_mode,
        model=model,
        base_url=base_url,
        viewer_user_id=viewer_user_id,
        viewer_username=viewer_username,
        viewer_tenant_id=viewer_tenant_id,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
    )
    specialists: dict[str, Any] = {}
    for sid in specialist_ids():
        specialists[sid] = build_gateway_executor(
            store,
            lang=lang,
            specialist=sid,
            profile_id=profile_id,
            openai_api_key=openai_api_key,
            llm_mode=llm_mode,
            model=model,
            base_url=base_url,
            viewer_user_id=viewer_user_id,
            viewer_username=viewer_username,
            viewer_tenant_id=viewer_tenant_id,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
        )
    return {"manager": manager, "specialists": specialists}


def build_ephemeral_executor(
    store: SqliteStore,
    *,
    lang: str = "zh",
    system_prompt: str,
    tool_policy: dict[str, Any] | None = None,
    profile_id: str | None = None,
    openai_api_key: str | None = None,
    llm_mode: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    viewer_user_id: str | None = None,
    viewer_username: str | None = None,
    viewer_tenant_id: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> Any:
    base_agent, _, _, _, _, _ = _build_executor_components(
        store,
        lang=lang,
        profile_id=profile_id,
        openai_api_key=openai_api_key,
        llm_mode=llm_mode,
        model=model,
        base_url=base_url,
        viewer_user_id=viewer_user_id,
        viewer_username=viewer_username,
        viewer_tenant_id=viewer_tenant_id,
    )
    declared = tool_policy if isinstance(tool_policy, dict) else {}
    allow_tags = [str(x) for x in (declared.get("allow_tags") or []) if str(x or "").strip()]
    allow_tools = [str(x) for x in (declared.get("allow_tools") or []) if str(x or "").strip()]
    tools = default_registry(
        expert="generalist+workspace+productivity",
        specialist="generalist",
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
        store=store,
        allow_tags=allow_tags,
        allow_tools=allow_tools,
    )
    return Agent(
        store=store,
        tools=tools,
        model=base_agent.model,
        system_prompt=str(system_prompt or "").strip(),
        lang=(lang or "zh").strip().lower(),
        llm_profile_mode=getattr(base_agent, "llm_profile_mode", None),
    )


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "build_ops_agent",
    "build_gateway_executor",
    "build_gateway_executors",
    "build_ephemeral_executor",
]
