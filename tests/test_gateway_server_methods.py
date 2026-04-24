from __future__ import annotations

from typing import Any

from oclaw.gateway.server_methods.agent import agent_handlers
from oclaw.gateway.server_methods.agents import agents_handlers
from oclaw.gateway.server_methods.chat import chat_handlers
from oclaw.gateway.server_methods.send import send_handlers
from oclaw.gateway.server_methods.image import image_handlers
from oclaw.gateway.server_methods.skills import skills_handlers
from oclaw.gateway.server_methods.system import system_handlers
from oclaw.gateway.server_methods.cron import cron_handlers
from oclaw.gateway.server_methods.devices import device_handlers
from oclaw.gateway.server_methods.models import models_handlers
from oclaw.gateway.server_methods.models_auth_status import (
    invalidate_model_auth_status_cache,
    models_auth_status_handlers,
)
from oclaw.gateway.server_methods.push import push_handlers
from oclaw.gateway.server_methods.channels import channels_handlers
from oclaw.gateway.server_methods.update import update_handlers
from oclaw.gateway.server_methods.voicewake import voicewake_handlers
from oclaw.gateway.server_methods.wizard import wizard_handlers
from oclaw.gateway.server_methods.tts import tts_handlers
from oclaw.gateway.server_methods.web import web_handlers
from oclaw.gateway.server_methods.tools_catalog import tools_catalog_handlers
from oclaw.gateway.server_methods.tools_effective import tools_effective_handlers
from oclaw.gateway.server_methods.talk import talk_handlers
from oclaw.gateway.server_methods.usage import usage_handlers
from oclaw.gateway.server_methods.exec_approvals import exec_approvals_handlers
from oclaw.gateway.server_methods.nodes_pending import node_pending_handlers
from oclaw.gateway.server_methods.nodes import node_handlers
from oclaw.gateway.server_methods.sessions import sessions_handlers
from oclaw.gateway.server_methods.doctor import doctor_handlers


def _call(handler, *, params: dict[str, Any], context: dict[str, Any] | None = None, client: dict[str, Any] | None = None):
    out: dict[str, Any] = {}

    def respond(ok, payload, error, meta):  # noqa: ANN001
        out["ok"] = ok
        out["payload"] = payload
        out["error"] = error
        out["meta"] = meta

    handler(
        {
            "params": params,
            "context": context if context is not None else {},
            "client": client if client is not None else {},
            "respond": respond,
        }
    )
    return out


def test_sessions_subscribe_and_unsubscribe_updates_subscriber_set() -> None:
    context: dict[str, Any] = {}
    client = {"conn_id": "c-1"}
    res1 = _call(sessions_handlers["sessions.subscribe"], params={}, context=context, client=client)
    assert res1["ok"] is True
    assert "c-1" in context["session_event_subscribers"]

    res2 = _call(sessions_handlers["sessions.unsubscribe"], params={}, context=context, client=client)
    assert res2["ok"] is True
    assert "c-1" not in context["session_event_subscribers"]


def test_agents_list_and_files_set_get_shapes() -> None:
    listed = _call(agents_handlers["agents.list"], params={})
    assert listed["ok"] is True
    assert isinstance((listed["payload"] or {}).get("agents"), list)

    set_out = _call(
        agents_handlers["agents.files.set"],
        params={"agentId": "main", "name": "SOUL.md", "content": "hello"},
    )
    assert set_out["ok"] is True
    file_payload = (set_out["payload"] or {}).get("file") or {}
    assert file_payload.get("name") == "SOUL.md"

    get_out = _call(agents_handlers["agents.files.get"], params={"agentId": "main", "name": "SOUL.md"})
    assert get_out["ok"] is True


def test_sessions_messages_subscribe_uses_key_alias() -> None:
    context: dict[str, Any] = {}
    client = {"conn_id": "c-2"}
    res = _call(
        sessions_handlers["sessions.messages.subscribe"],
        params={"key": "sess-1"},
        context=context,
        client=client,
    )
    assert res["ok"] is True
    subscribers = context["session_message_subscribers"]["sess-1"]
    assert "c-2" in subscribers


def test_chat_send_requires_session_key_or_key() -> None:
    bad = _call(chat_handlers["chat.send"], params={"message": "hi"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    good = _call(chat_handlers["chat.send"], params={"key": "sess-x", "message": "hi", "idempotencyKey": "idem-x"})
    assert good["ok"] is True
    assert good["payload"]["status"] == "started"
    assert good["payload"]["runId"] == "idem-x"


def test_chat_send_telegram_transport_fields_are_normalized() -> None:
    out = _call(
        chat_handlers["chat.send"],
        params={
            "key": "sess-telegram",
            "message": "hi",
            "idempotencyKey": "idem-chat-tg",
            "channel": "telegram",
            "to": "telegram:group:-100123456789:topic:9",
            "replyToId": "11",
        },
    )
    assert out["ok"] is True
    payload = out["payload"] or {}
    assert payload.get("channel") == "telegram"
    assert payload.get("to") == "telegram:group:-100123456789:topic:9"
    assert payload.get("threadId") == 9
    assert payload.get("replyToMessageId") == 11
    target = payload.get("target") or {}
    assert target.get("chatId") == "-100123456789"
    assert target.get("chatType") == "group"


def test_chat_send_forwards_normalized_telegram_fields_to_enqueue() -> None:
    captured: dict[str, Any] = {}

    def _enqueue(session_key: str, message: str, run_id: str, forwarded_params: dict[str, Any]) -> bool:
        captured["session_key"] = session_key
        captured["message"] = message
        captured["run_id"] = run_id
        captured["params"] = dict(forwarded_params)
        return True

    out = _call(
        chat_handlers["chat.send"],
        params={
            "key": "sess-enqueue",
            "message": "hello",
            "idempotencyKey": "idem-enqueue-tg",
            "channel": "telegram",
            "to": "telegram:group:-100999:topic:5",
            "replyToId": "14",
        },
        context={"enqueue_chat_send": _enqueue},
    )
    assert out["ok"] is True
    forwarded = captured.get("params") or {}
    assert forwarded.get("to") == "telegram:group:-100999:topic:5"
    assert forwarded.get("threadId") == 5
    assert forwarded.get("replyToMessageId") == 14
    target = forwarded.get("target") or {}
    assert target.get("chatId") == "-100999"
    assert target.get("chatType") == "group"


def test_agent_dedupe_then_wait_reads_cached_status() -> None:
    context: dict[str, Any] = {"dedupe": {}}
    res1 = _call(
        agent_handlers["agent"],
        params={"message": "hello", "idempotencyKey": "run-1"},
        context=context,
    )
    assert res1["ok"] is True

    res2 = _call(
        agent_handlers["agent"],
        params={"message": "hello", "idempotencyKey": "run-1"},
        context=context,
    )
    assert res2["ok"] is True
    assert (res2["meta"] or {}).get("cached") is True

    wait = _call(agent_handlers["agent.wait"], params={"runId": "run-1"}, context=context)
    assert wait["ok"] is True
    assert wait["payload"]["runId"] == "run-1"


def test_send_dedupe_returns_cached_meta() -> None:
    context: dict[str, Any] = {"dedupe": {}}
    first = _call(
        send_handlers["send"],
        params={"to": "u1", "message": "hi", "idempotencyKey": "idem-s1", "channel": "telegram"},
        context=context,
    )
    assert first["ok"] is True
    assert (first["payload"] or {}).get("runId") == "idem-s1"

    second = _call(
        send_handlers["send"],
        params={"to": "u1", "message": "hi", "idempotencyKey": "idem-s1", "channel": "telegram"},
        context=context,
    )
    assert second["ok"] is True
    assert (second["meta"] or {}).get("cached") is True


def test_send_telegram_normalizes_target_and_thread_params() -> None:
    context: dict[str, Any] = {"dedupe": {}}
    out = _call(
        send_handlers["send"],
        params={
            "to": "telegram:group:-100987654321:topic:42",
            "message": "hello",
            "idempotencyKey": "idem-tg-1",
            "channel": "telegram",
            "replyToId": "77",
        },
        context=context,
    )
    assert out["ok"] is True
    payload = out["payload"] or {}
    assert payload.get("to") == "telegram:group:-100987654321:topic:42"
    assert payload.get("threadId") == 42
    assert payload.get("replyToMessageId") == 77
    target = payload.get("target") or {}
    assert target.get("chatId") == "-100987654321"
    assert target.get("chatType") == "group"
    assert target.get("messageThreadId") == 42


def test_sessions_send_telegram_target_is_normalized() -> None:
    out = _call(
        sessions_handlers["sessions.send"],
        params={
            "sessionKey": "sess-1",
            "message": "hello",
            "channel": "telegram",
            "to": "telegram:group:-100987654321:topic:7",
            "replyToId": "3",
        },
    )
    assert out["ok"] is True
    payload = out["payload"] or {}
    assert payload.get("channel") == "telegram"
    assert payload.get("to") == "telegram:group:-100987654321:topic:7"
    assert payload.get("threadId") == 7
    assert payload.get("replyToMessageId") == 3
    target = payload.get("target") or {}
    assert target.get("chatId") == "-100987654321"
    assert target.get("chatType") == "group"


class _MemStore:
    def __init__(self) -> None:
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str) -> str | None:  # noqa: ANN001
        return self._settings.get(str(key))

    def set_setting(self, key: str, value: str) -> None:  # noqa: ANN001
        self._settings[str(key)] = str(value)


def test_skills_status_requires_store_then_lists_skills() -> None:
    no_store = _call(skills_handlers["skills.status"], params={}, context={})
    assert no_store["ok"] is False
    assert no_store["error"]["code"] == "UNAVAILABLE"

    store = _MemStore()
    ok = _call(skills_handlers["skills.status"], params={}, context={"store": store})
    assert ok["ok"] is True
    payload = ok["payload"] or {}
    assert isinstance(payload.get("skills"), list)
    # Repo ships oclaw/skills/{main,coding,social}
    names = {str(x.get("name")) for x in payload["skills"] if isinstance(x, dict)}
    assert "main" in names


def test_system_set_heartbeats_requires_boolean() -> None:
    bad = _call(system_handlers["set-heartbeats"], params={"enabled": "yes"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    ok = _call(system_handlers["set-heartbeats"], params={"enabled": True})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("enabled") is True


def test_system_event_requires_text() -> None:
    bad = _call(system_handlers["system-event"], params={})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"


def test_cron_update_requires_id() -> None:
    bad = _call(cron_handlers["cron.update"], params={"patch": {"name": "x"}})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"


def test_cron_add_and_run_fallback() -> None:
    add = _call(cron_handlers["cron.add"], params={"name": "job-a", "schedule": "*/5 * * * *"})
    assert add["ok"] is True
    assert (add["payload"] or {}).get("id") is not None

    run = _call(cron_handlers["cron.run"], params={"id": "job-a", "mode": "force"})
    assert run["ok"] is True
    assert (run["payload"] or {}).get("ran") is True


def test_image_generate_falls_back_to_registered_openai_provider() -> None:
    # Get providers via plugin load, then inject into gateway context.
    from oclaw.gateway.server_plugins import load_gateway_plugins

    plugin_out = load_gateway_plugins(
        cfg={"plugins": {"enabled": ["openai"]}},
        workspace_dir=".",
        log={},
        core_gateway_handlers={},
        base_methods=["ping"],
    )
    providers = plugin_out.plugin_registry.get("image_generation_providers") or []
    res = _call(
        image_handlers["image.generate"],
        params={"prompt": "a cat", "provider": "openai", "size": "1024x1024"},
        context={"image_generation_providers": providers},
    )
    assert res["ok"] is True
    payload = res["payload"] or {}
    assert payload.get("ok") is True
    assert payload.get("provider") == "openai"
    assert payload.get("model") == "gpt-image-1"
    assert payload.get("prompt") == "a cat"


def test_image_generate_rejects_unknown_provider_with_not_found() -> None:
    res = _call(
        image_handlers["image.generate"],
        params={"prompt": "a cat", "provider": "missing-provider"},
        context={"image_generation_providers": []},
    )
    assert res["ok"] is False
    assert (res["error"] or {}).get("code") == "NOT_FOUND"


def test_image_generate_rejects_invalid_optional_params() -> None:
    bad_provider = _call(
        image_handlers["image.generate"],
        params={"prompt": "x", "provider": "   "},
    )
    assert bad_provider["ok"] is False
    assert (bad_provider["error"] or {}).get("code") == "INVALID_REQUEST"

    bad_size = _call(
        image_handlers["image.generate"],
        params={"prompt": "x", "size": 1024},
    )
    assert bad_size["ok"] is False
    assert (bad_size["error"] or {}).get("code") == "INVALID_REQUEST"


def test_image_generate_prefers_configured_default_provider() -> None:
    providers = [
        {"id": "openai", "generate": lambda **kw: {"model": "gpt-image-1", "prompt": kw.get("prompt")}},
        {"id": "alt", "generate": lambda **kw: {"model": "alt-image", "prompt": kw.get("prompt")}},
    ]
    res = _call(
        image_handlers["image.generate"],
        params={"prompt": "city skyline"},
        context={
            "image_generation_providers": providers,
            "config": {"image": {"defaultProvider": "alt"}},
        },
    )
    assert res["ok"] is True
    payload = res["payload"] or {}
    assert payload.get("provider") == "alt"
    assert payload.get("model") == "alt-image"


def test_image_generate_uses_priority_list_when_no_explicit_or_default() -> None:
    providers = [
        {"id": "openai", "generate": lambda **kw: {"model": "gpt-image-1", "prompt": kw.get("prompt")}},
        {"id": "foo", "generate": lambda **kw: {"model": "foo-image", "prompt": kw.get("prompt")}},
    ]
    res = _call(
        image_handlers["image.generate"],
        params={"prompt": "forest"},
        context={
            "image_generation_providers": providers,
            "config": {"image": {"providerPriority": ["bar", "foo", "openai"]}},
        },
    )
    assert res["ok"] is True
    payload = res["payload"] or {}
    assert payload.get("provider") == "foo"
    assert payload.get("model") == "foo-image"


def test_image_generate_filters_non_image_capability_providers() -> None:
    providers = [
        {
            "id": "text-only",
            "capabilities": {"image_generation": False},
            "generate": lambda **kw: {"model": "should-not-use", "prompt": kw.get("prompt")},
        },
        {
            "id": "image-ok",
            "capabilities": {"image_generation": True},
            "generate": lambda **kw: {"model": "ok-image", "prompt": kw.get("prompt")},
        },
    ]
    res = _call(
        image_handlers["image.generate"],
        params={"prompt": "mountain"},
        context={"image_generation_providers": providers},
    )
    assert res["ok"] is True
    payload = res["payload"] or {}
    assert payload.get("provider") == "image-ok"
    assert payload.get("model") == "ok-image"


def test_channels_status_exposes_image_generation_providers_from_context() -> None:
    providers = [{"id": "openai", "label": "OpenAI Images"}, {"id": "x"}]
    res = _call(
        channels_handlers["channels.status"],
        params={"probe": False},
        context={"image_generation_providers": providers},
    )
    assert res["ok"] is True
    runtime = (res["payload"] or {}).get("runtime") or {}
    assert isinstance(runtime.get("image_generation_providers"), list)
    assert runtime["image_generation_providers"][0]["id"] == "openai"


def test_doctor_memory_status_shape_and_hook() -> None:
    out = _call(doctor_handlers["doctor.memory.status"], params={})
    assert out["ok"] is True
    payload = out["payload"] or {}
    assert payload.get("agentId") == "main"
    assert isinstance(payload.get("dreaming"), dict)

    ctx = {"doctor_memory_status": lambda: {"agentId": "custom", "embedding": {"ok": False}}}
    hooked = _call(doctor_handlers["doctor.memory.status"], params={}, context=ctx)
    assert hooked["ok"] is True
    assert (hooked["payload"] or {}).get("agentId") == "custom"


def test_device_pair_remove_denied_for_cross_device_non_admin() -> None:
    res = _call(
        device_handlers["device.pair.remove"],
        params={"deviceId": "dev-b"},
        client={"connect": {"device": {"id": "dev-a"}, "scopes": ["operator.write"]}},
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "INVALID_REQUEST"


def test_device_token_rotate_requires_fields() -> None:
    bad = _call(device_handlers["device.token.rotate"], params={"deviceId": "dev-a"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    ok = _call(device_handlers["device.token.rotate"], params={"deviceId": "dev-a", "role": "worker"})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("deviceId") == "dev-a"


def test_models_list_fallback_and_filtered() -> None:
    fallback = _call(models_handlers["models.list"], params={}, context={})
    assert fallback["ok"] is True
    assert (fallback["payload"] or {}).get("models") == []

    context = {
        "loadGatewayModelCatalog": lambda: [{"provider": "openai", "model": "gpt-4.1"}, {"provider": "x", "model": "y"}],
        "filterAllowedModels": lambda rows: [r for r in rows if r.get("provider") == "openai"],
    }
    filtered = _call(models_handlers["models.list"], params={}, context=context)
    assert filtered["ok"] is True
    models = (filtered["payload"] or {}).get("models") or []
    assert len(models) == 1
    assert models[0]["provider"] == "openai"


def test_models_auth_status_cache_and_refresh() -> None:
    invalidate_model_auth_status_cache()
    calls = {"n": 0}

    def _loader():  # noqa: ANN001
        calls["n"] += 1
        return [
            {
                "provider": "openai",
                "displayName": "OpenAI",
                "status": "ok",
                "profiles": [{"profileId": "p1", "type": "oauth", "status": "ok"}],
            }
        ]

    ctx = {"load_models_auth_status": _loader}
    first = _call(models_auth_status_handlers["models.authStatus"], params={}, context=ctx)
    second = _call(models_auth_status_handlers["models.authStatus"], params={}, context=ctx)
    refreshed = _call(models_auth_status_handlers["models.authStatus"], params={"refresh": True}, context=ctx)

    assert first["ok"] is True
    assert second["ok"] is True
    assert refreshed["ok"] is True
    assert calls["n"] == 2
    assert (second["meta"] or {}).get("cached") is True


def test_push_test_requires_node_id() -> None:
    bad = _call(push_handlers["push.test"], params={})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    ok = _call(push_handlers["push.test"], params={"nodeId": "node-1"})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("nodeId") == "node-1"


def test_update_run_returns_result_shape() -> None:
    out = _call(update_handlers["update.run"], params={"timeoutMs": 5000, "sessionKey": "main"})
    assert out["ok"] is True
    payload = out["payload"] or {}
    assert "result" in payload
    assert "sentinel" in payload


def test_voicewake_set_requires_triggers_array() -> None:
    bad = _call(voicewake_handlers["voicewake.set"], params={"triggers": "hey"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"
    ok = _call(voicewake_handlers["voicewake.set"], params={"triggers": ["Hey OpenClaw", "  ", "hey openclaw"]})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("triggers") == ["Hey OpenClaw"]


def test_wizard_start_next_status_cancel_flow() -> None:
    context: dict[str, Any] = {}
    started = _call(wizard_handlers["wizard.start"], params={"mode": "quick"}, context=context)
    assert started["ok"] is True
    session_id = str((started["payload"] or {}).get("sessionId") or "")
    assert session_id != ""
    status = _call(wizard_handlers["wizard.status"], params={"sessionId": session_id}, context=context)
    assert status["ok"] is True
    assert (status["payload"] or {}).get("status") == "running"
    nxt = _call(
        wizard_handlers["wizard.next"],
        params={"sessionId": session_id, "answer": {"stepId": "step-1", "value": "x"}},
        context=context,
    )
    assert nxt["ok"] is True
    cancelled = _call(wizard_handlers["wizard.cancel"], params={"sessionId": session_id}, context=context)
    assert cancelled["ok"] is True
    assert (cancelled["payload"] or {}).get("status") == "cancelled"


def test_tts_convert_requires_text() -> None:
    bad = _call(tts_handlers["tts.convert"], params={})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"
    ok = _call(tts_handlers["tts.convert"], params={"text": "hello"})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("audioPath")


def test_web_login_provider_required() -> None:
    bad = _call(web_handlers["web.login.start"], params={})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    context = {
        "resolve_web_login_provider": lambda: {
            "id": "wechat",
            "loginWithQrStart": lambda _p: {"connected": False, "qrDataUrl": "data:image/png;base64,abc"},
            "loginWithQrWait": lambda _p: {"connected": True},
        }
    }
    started = _call(web_handlers["web.login.start"], params={}, context=context)
    assert started["ok"] is True
    waited = _call(web_handlers["web.login.wait"], params={}, context=context)
    assert waited["ok"] is True


def test_tools_catalog_and_effective_basic_shapes() -> None:
    cat = _call(tools_catalog_handlers["tools.catalog"], params={"includePlugins": False})
    assert cat["ok"] is True
    assert (cat["payload"] or {}).get("agentId")
    assert isinstance((cat["payload"] or {}).get("groups"), list)

    eff_bad = _call(tools_effective_handlers["tools.effective"], params={})
    assert eff_bad["ok"] is False
    assert eff_bad["error"]["code"] == "INVALID_REQUEST"

    eff = _call(tools_effective_handlers["tools.effective"], params={"sessionKey": "main"})
    assert eff["ok"] is True
    assert (eff["payload"] or {}).get("sessionKey") == "main"


def test_talk_speak_requires_text_and_mode_shape() -> None:
    bad = _call(talk_handlers["talk.speak"], params={})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_REQUEST"

    ok = _call(talk_handlers["talk.speak"], params={"text": "hi"})
    assert ok["ok"] is True
    assert (ok["payload"] or {}).get("audioBase64")

    mode = _call(talk_handlers["talk.mode"], params={"enabled": True})
    assert mode["ok"] is True
    assert (mode["payload"] or {}).get("enabled") is True


def test_usage_handlers_basic_shapes_and_cache() -> None:
    status = _call(usage_handlers["usage.status"], params={})
    assert status["ok"] is True
    assert "providers" in (status["payload"] or {})

    calls = {"n": 0}

    def _cost_loader(req: dict[str, Any]) -> dict[str, Any]:
        calls["n"] += 1
        return {"startMs": req["startMs"], "endMs": req["endMs"], "totals": {"totalCost": 1}}

    ctx = {"load_cost_usage_summary": _cost_loader}
    c1 = _call(usage_handlers["usage.cost"], params={"days": 1}, context=ctx)
    c2 = _call(usage_handlers["usage.cost"], params={"days": 1}, context=ctx)
    assert c1["ok"] is True
    assert c2["ok"] is True
    assert calls["n"] == 1
    assert (c2["meta"] or {}).get("cached") is True

    sess_bad = _call(usage_handlers["sessions.usage"], params={"key": 123})
    assert sess_bad["ok"] is False
    assert sess_bad["error"]["code"] == "INVALID_REQUEST"
    sess_ok = _call(usage_handlers["sessions.usage"], params={"key": "sess-1", "limit": 5})
    assert sess_ok["ok"] is True
    assert isinstance((sess_ok["payload"] or {}).get("sessions"), list)


def test_exec_approvals_base_hash_and_node_shapes() -> None:
    context: dict[str, Any] = {}
    got = _call(exec_approvals_handlers["exec.approvals.get"], params={}, context=context)
    assert got["ok"] is True
    payload = got["payload"] or {}
    assert "path" in payload and "file" in payload

    bad_set = _call(exec_approvals_handlers["exec.approvals.set"], params={}, context=context)
    assert bad_set["ok"] is False
    assert bad_set["error"]["code"] == "INVALID_REQUEST"

    set1 = _call(
        exec_approvals_handlers["exec.approvals.set"],
        params={"file": {"allow": ["echo"]}},
        context=context,
    )
    assert set1["ok"] is True
    h = str(((set1["payload"] or {}).get("hash") or "")).strip()
    assert h != ""

    stale = _call(
        exec_approvals_handlers["exec.approvals.set"],
        params={"file": {"allow": ["ls"]}, "baseHash": "wrong-hash"},
        context=context,
    )
    assert stale["ok"] is False
    assert stale["error"]["code"] == "INVALID_REQUEST"

    node_bad = _call(exec_approvals_handlers["exec.approvals.node.get"], params={"nodeId": ""}, context=context)
    assert node_bad["ok"] is False
    assert node_bad["error"]["code"] == "INVALID_REQUEST"

    node_ok = _call(exec_approvals_handlers["exec.approvals.node.get"], params={"nodeId": "n1"}, context=context)
    assert node_ok["ok"] is True


def test_node_pending_enqueue_then_drain() -> None:
    context: dict[str, Any] = {}
    enqueue = _call(
        node_pending_handlers["node.pending.enqueue"],
        params={"nodeId": "n1", "type": "sync", "wake": True},
        context=context,
    )
    assert enqueue["ok"] is True
    assert (enqueue["payload"] or {}).get("wakeTriggered") is True

    # drain requires connected client identity
    no_client = _call(node_pending_handlers["node.pending.drain"], params={}, context=context)
    assert no_client["ok"] is False
    assert no_client["error"]["code"] == "INVALID_REQUEST"

    drained = _call(
        node_pending_handlers["node.pending.drain"],
        params={"maxItems": 10},
        context=context,
        client={"connect": {"device": {"id": "n1"}}},
    )
    assert drained["ok"] is True
    payload = drained["payload"] or {}
    assert payload.get("nodeId") == "n1"
    assert int(payload.get("count") or 0) >= 1


def test_node_pair_and_invoke_basics() -> None:
    context: dict[str, Any] = {}
    req = _call(
        node_handlers["node.pair.request"],
        params={"nodeId": "node-1", "displayName": "iPhone"},
        context=context,
    )
    assert req["ok"] is True
    request_id = str(((req["payload"] or {}).get("request") or {}).get("requestId") or "")
    assert request_id != ""

    approved = _call(node_handlers["node.pair.approve"], params={"requestId": request_id}, context=context)
    assert approved["ok"] is True

    listed = _call(node_handlers["node.list"], params={}, context=context)
    assert listed["ok"] is True
    assert isinstance((listed["payload"] or {}).get("nodes"), list)

    bad_invoke = _call(
        node_handlers["node.invoke"],
        params={"nodeId": "node-1", "command": "system.execApprovals.get"},
        context=context,
    )
    assert bad_invoke["ok"] is False
    assert bad_invoke["error"]["code"] == "INVALID_REQUEST"

    ok_invoke = _call(
        node_handlers["node.invoke"],
        params={"nodeId": "node-1", "command": "screen.capture"},
        context=context,
    )
    assert ok_invoke["ok"] is True




