from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from svc.llm.tool_wire_policy import (
    SETTINGS_KEY_PENALTY_STATE,
    migrate_legacy_penalty_store,
    prepare_openai_tools_for_llm_api,
)


class FakeToolStore:
    """Minimal store stub for ``prepare_openai_tools_for_llm_api``."""

    def __init__(self, usage_map: dict, penalty_state: dict | None = None) -> None:
        self.usage_map = dict(usage_map)
        self._penalty_json = json.dumps(penalty_state or {})
        self.last_penalty_saved: str | None = None

    def list_mcp_tool_aggregate_usage(self) -> dict:
        return dict(self.usage_map)

    def get_setting(self, key: str) -> str | None:
        if key == SETTINGS_KEY_PENALTY_STATE:
            return self._penalty_json
        return None

    def set_setting(self, key: str, val: str) -> None:
        if key == SETTINGS_KEY_PENALTY_STATE:
            self._penalty_json = val
            self.last_penalty_saved = val


def _fn(name: str, *, desc: str = "hello") -> dict:
    props: dict = {"fld": {"type": "string", "description": "inner"}}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props},
        },
    }


def _names(tools: list[dict]) -> list[str]:
    out: list[str] = []
    for t in tools:
        fn = t.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            out.append(str(fn["name"]))
    return out


def _iso_hours_ago(h: float) -> str:
    n = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    return (n - timedelta(hours=h)).isoformat()


class ToolWirePolicyTests(unittest.TestCase):
    def test_builtin_tools_always_full(self) -> None:
        ts = _iso_hours_ago(1.0)
        usage = {
            "mcp__rank__1": {"count": 400, "last_ts": ts},
            "mcp__rank__2": {"count": 300, "last_ts": ts},
            "mcp__rank__3": {"count": 200, "last_ts": ts},
            "mcp__srv__x": {"count": 1, "last_ts": ts},
        }
        tools = [_fn("read_file"), _fn("mcp__rank__1"), _fn("mcp__rank__2"), _fn("mcp__rank__3"), _fn("mcp__srv__x")]
        st = FakeToolStore(usage)
        with patch("svc.llm.tool_wire_policy._utc_now", return_value=datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)):
            with patch.dict("os.environ", {"OPS_MCP_WIRE_TOP_N_FULL": "3"}, clear=False):
                out = prepare_openai_tools_for_llm_api(
                    tools,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    max_json_bytes=None,
                    store=st,
                )
        by_name = {str(t["function"]["name"]): t for t in out if t.get("type") == "function"}
        self.assertIn("inner", json.dumps(by_name["read_file"]))
        self.assertNotIn("inner", json.dumps(by_name["mcp__srv__x"]))

    def test_graduated_minimal_below_top_n(self) -> None:
        ts = _iso_hours_ago(0.5)
        usage = {
            "mcp__p__a": {"count": 100, "last_ts": ts},
            "mcp__p__b": {"count": 90, "last_ts": ts},
            "mcp__p__c": {"count": 80, "last_ts": ts},
            "mcp__p__d": {"count": 70, "last_ts": ts},
        }
        tools = [_fn("mcp__p__a"), _fn("mcp__p__b"), _fn("mcp__p__c"), _fn("mcp__p__d")]
        st = FakeToolStore(usage)
        fixed = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
        with patch("svc.llm.tool_wire_policy._utc_now", return_value=fixed):
            with patch.dict(
                "os.environ",
                {
                    "OPS_MCP_WIRE_TOP_N_FULL": "3",
                    "OPS_MCP_WIRE_MEDIUM_RANK_START": "999",
                    "OPS_MCP_WIRE_MEDIUM_RANK_END": "999",
                },
                clear=False,
            ):
                out = prepare_openai_tools_for_llm_api(
                    tools,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    max_json_bytes=None,
                    store=st,
                )
        by_name = {str(t["function"]["name"]): t for t in out}
        self.assertIn("properties", by_name["mcp__p__a"]["function"]["parameters"])
        self.assertIn("properties", by_name["mcp__p__b"]["function"]["parameters"])
        self.assertIn("properties", by_name["mcp__p__c"]["function"]["parameters"])
        self.assertEqual(by_name["mcp__p__d"]["function"]["parameters"].get("additionalProperties"), True)

    def test_never_logged_mcp_not_omitted(self) -> None:
        tools = [_fn("mcp__ghost__z")]
        st = FakeToolStore({})
        out = prepare_openai_tools_for_llm_api(
            tools,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            max_json_bytes=None,
            store=st,
        )
        self.assertEqual(_names(out), ["mcp__ghost__z"])

    def test_stale_penalty_then_release(self) -> None:
        t0 = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
        stale_ts = (t0 - timedelta(hours=4)).isoformat()
        usage = {
            "mcp__st__fill1": {"count": 900, "last_ts": stale_ts},
            "mcp__st__fill2": {"count": 800, "last_ts": stale_ts},
            "mcp__st__fill3": {"count": 700, "last_ts": stale_ts},
            "mcp__st__old": {"count": 5, "last_ts": stale_ts},
        }
        tools = [_fn("mcp__st__fill1"), _fn("mcp__st__fill2"), _fn("mcp__st__fill3"), _fn("mcp__st__old")]
        st = FakeToolStore(usage)

        with patch.dict(
            "os.environ",
            {"OPS_MCP_WIRE_STALE_HOURS": "3", "OPS_MCP_WIRE_TOP_N_FULL": "3"},
            clear=False,
        ):
            with patch("svc.llm.tool_wire_policy._utc_now", return_value=t0):
                out1 = prepare_openai_tools_for_llm_api(
                    tools,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    max_json_bytes=None,
                    store=st,
                )
                self.assertEqual(_names(out1), ["mcp__st__fill1", "mcp__st__fill2", "mcp__st__fill3"])

                pen = json.loads(st.last_penalty_saved or "{}")
                self.assertEqual(pen["mcp__st__old"]["phase"], "active")

                t_late = t0 + timedelta(minutes=31)
                with patch("svc.llm.tool_wire_policy._utc_now", return_value=t_late):
                    out2 = prepare_openai_tools_for_llm_api(
                        tools,
                        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        max_json_bytes=None,
                        store=st,
                    )
                want = ["mcp__st__fill1", "mcp__st__fill2", "mcp__st__fill3", "mcp__st__old"]
                self.assertEqual(_names(out2), want)
                pen2 = json.loads(st.last_penalty_saved or "{}")
                self.assertEqual(pen2["mcp__st__old"]["phase"], "done")

    def test_wave_ts_change_clears_penalty(self) -> None:
        t0 = datetime(2026, 4, 19, 15, 0, 0, tzinfo=timezone.utc)
        old_ts = (t0 - timedelta(hours=5)).isoformat()
        usage1 = {"mcp__w__x": {"count": 1, "last_ts": old_ts}}
        penalty1 = {"mcp__w__x": {"phase": "done", "wave_ts": old_ts}}
        tools = [_fn("mcp__w__x")]
        st = FakeToolStore(usage1, penalty1)

        new_ts = (t0 - timedelta(minutes=30)).isoformat()
        usage2 = {"mcp__w__x": {"count": 2, "last_ts": new_ts}}
        st.usage_map = usage2

        with patch.dict(
            "os.environ",
            {"OPS_MCP_WIRE_STALE_HOURS": "3", "OPS_MCP_WIRE_TOP_N_FULL": "3"},
            clear=False,
        ):
            with patch("svc.llm.tool_wire_policy._utc_now", return_value=t0):
                out = prepare_openai_tools_for_llm_api(
                    tools,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    max_json_bytes=None,
                    store=st,
                )
        pen = json.loads(st.last_penalty_saved or "{}")
        self.assertNotIn("mcp__w__x", pen)
        self.assertEqual(_names(out), ["mcp__w__x"])

    def test_migrate_legacy_penalty_store(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        raw = {
            "legacy_active": {"omit_until": future, "wave_ts": "x"},
            "legacy_done": {"omit_until": past, "wave_ts": "y"},
        }
        mig = migrate_legacy_penalty_store(raw)
        self.assertEqual(mig["legacy_active"]["phase"], "active")
        self.assertEqual(mig["legacy_done"]["phase"], "done")


if __name__ == "__main__":
    unittest.main()
