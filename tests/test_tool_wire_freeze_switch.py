from __future__ import annotations

from runtime import direct_loop as dl


class _DummyStore:
    def __init__(self, settings: dict[str, str] | None = None):
        self.settings = dict(settings or {})

    def get_setting(self, key: str) -> str:
        return str(self.settings.get(key, ""))


def test_tool_wire_freeze_default_on(monkeypatch) -> None:
    monkeypatch.setattr(dl, "_prepare_llm_tools", lambda **kwargs: [])
    monkeypatch.setenv("AIA_TOOL_WIRE_FROZEN_ON_STARTUP", "")
    store = _DummyStore()
    _ = dl.warm_tool_wire_cache(store=store, tools=object(), base_url="", roles=["generalist"])
    st = dl.tool_wire_freeze_status(store=store)
    assert st["enabled"] is True
    assert st["frozen"] is True


def test_tool_wire_freeze_disabled_by_setting(monkeypatch) -> None:
    monkeypatch.setattr(dl, "_prepare_llm_tools", lambda **kwargs: [])
    store = _DummyStore({"AIA_TOOL_WIRE_FROZEN_ON_STARTUP": "0"})
    _ = dl.warm_tool_wire_cache(store=store, tools=object(), base_url="", roles=["generalist"])
    st = dl.tool_wire_freeze_status(store=store)
    assert st["enabled"] is False
    assert st["frozen"] is False


def test_warm_tool_wire_cache_clears_frozen_stale_entries(monkeypatch) -> None:
    """Regression: prewarm must rebuild after MCP sync; frozen mode used to return stale wire."""
    calls = {"n": 0}

    def _prep(**_kwargs):
        calls["n"] += 1
        return [{"type": "function", "function": {"name": f"tool_{calls['n']}"}}]

    monkeypatch.setattr(dl, "_prepare_llm_tools", _prep)
    monkeypatch.setenv("AIA_TOOL_WIRE_FROZEN_ON_STARTUP", "1")
    store = _DummyStore({"AIA_TOOL_WIRE_FROZEN_ON_STARTUP": "1"})
    with dl._TOOL_WIRE_CACHE_LOCK:
        dl._TOOL_WIRE_FROZEN_SIGNATURE = "rt=1|stale"
        dl._TOOL_WIRE_CACHE.clear()
        dl._TOOL_WIRE_CACHE["poison"] = (0.0, [{"type": "function", "function": {"name": "old"}}])
    out = dl.warm_tool_wire_cache(store=store, tools=object(), base_url="", roles=["generalist", "ops"])
    assert calls["n"] == 2
    assert int(out.get("cache_cleared") or 0) == 1
    assert "poison" not in dl._TOOL_WIRE_CACHE
    st = dl.tool_wire_freeze_status(store=store)
    assert st["frozen"] is True
    assert st["last_warm_count"] == 2
