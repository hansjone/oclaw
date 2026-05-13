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
    _ = dl.warm_tool_wire_cache(store=store, tools=object(), base_url="", roles=["manager"])
    st = dl.tool_wire_freeze_status(store=store)
    assert st["enabled"] is True
    assert st["frozen"] is True


def test_tool_wire_freeze_disabled_by_setting(monkeypatch) -> None:
    monkeypatch.setattr(dl, "_prepare_llm_tools", lambda **kwargs: [])
    store = _DummyStore({"AIA_TOOL_WIRE_FROZEN_ON_STARTUP": "0"})
    _ = dl.warm_tool_wire_cache(store=store, tools=object(), base_url="", roles=["manager"])
    st = dl.tool_wire_freeze_status(store=store)
    assert st["enabled"] is False
    assert st["frozen"] is False
