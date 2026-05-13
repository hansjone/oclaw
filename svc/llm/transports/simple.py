from __future__ import annotations

import json
import re
from typing import Any, Optional
from collections.abc import Callable

from svc.llm.transports.base import ChatModel, LLMResponse, LLMToolCall


class StaticTextChatModel(ChatModel):
    def __init__(self, text: str):
        self._text = text or ""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        if on_token and self._text:
            on_token(self._text)
        return LLMResponse(content=self._text, tool_calls=[])


class RuleBasedChatModel(ChatModel):
    _IP_RE = re.compile(
        r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})|(?P<ipv6>(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F]{0,4})"
    )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        def make_call(name: str, arguments: dict[str, Any]) -> LLMResponse:
            return LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id=f"rb_{name}_1", name=name, arguments=arguments)],
            )

        def emit(resp: LLMResponse) -> LLMResponse:
            if on_token and (resp.content or "").strip():
                on_token(resp.content)
            return resp

        if messages:
            last = messages[-1]
            if last.get("role") == "tool":
                raw = str(last.get("content") or "")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"ok": True, "raw": raw}

                if isinstance(data, dict) and data.get("ok") is False:
                    return emit(LLMResponse(content=f"工具执行失败：{data.get('error')}", tool_calls=[]))

                if isinstance(data, dict) and "route" in data:
                    r = data.get("route") or {}
                    return emit(
                        LLMResponse(
                            content=f"路由查询结果：目的 {data.get('destination')} 命中 {r.get('prefix')}，下一跳 {r.get('next_hop')}，出接口 {r.get('out_if')}。",
                            tool_calls=[],
                        )
                    )

                if isinstance(data, dict) and "hops" in data:
                    hops = data.get("hops") or []
                    return emit(
                        LLMResponse(
                            content=f"路径计算结果：{data.get('src')} → {data.get('dst')} 共 {data.get('hop_count')} 跳，路径为：{' -> '.join(map(str, hops))}",
                            tool_calls=[],
                        )
                    )

                if isinstance(data, dict) and "diff" in data:
                    diff = data.get("diff") or ""
                    if not diff:
                        return emit(LLMResponse(content="配置对比结果：两段配置一致。", tool_calls=[]))
                    return emit(LLMResponse(content=f"配置对比结果：\n\n```diff\n{diff}\n```", tool_calls=[]))

                if isinstance(data, dict) and "level_count" in data:
                    lc = data.get("level_count") or {}
                    return emit(LLMResponse(content=f"日志分析结果：统计 {lc}。建议优先查看 ERROR 样例与日志尾部定位根因。", tool_calls=[]))

                if isinstance(data, dict) and "reachable" in data:
                    reach = bool(data.get("reachable"))
                    avg = data.get("avg_ms")
                    if reach:
                        tail = f"平均时延 {avg}ms" if isinstance(avg, int) else "时延解析失败"
                        return emit(LLMResponse(content=f"设备状态：可达，{tail}。", tool_calls=[]))
                    return emit(LLMResponse(content="设备状态：不可达。建议检查 ACL/路由/DNS/防火墙策略，并确认目标在线。", tool_calls=[]))

                return emit(LLMResponse(content=f"工具执行结果：{json.dumps(data, ensure_ascii=False)}", tool_calls=[]))

        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, list):
                    texts = [item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text"]
                    last_user = "\n".join(texts)
                else:
                    last_user = str(content or "")
                break

        m = self._IP_RE.search(last_user)
        if "路由" in last_user and m:
            ip = m.group("ip") or m.group("ipv6")
            return make_call("query_route", {"destination": ip})

        if ("路径" in last_user or "链路" in last_user) and ("到" in last_user or "->" in last_user):
            m2 = re.search(r"([A-Za-z0-9_-]+)\s*(?:到|->)\s*([A-Za-z0-9_-]+)", last_user)
            if m2:
                src, dst = m2.group(1), m2.group(2)
                return make_call("get_path", {"src": src, "dst": dst})

        if "对比" in last_user or "diff" in last_user.lower():
            if "left:" in last_user.lower() and "right:" in last_user.lower():
                left = last_user.split("left:", 1)[1].split("right:", 1)[0].strip()
                right = last_user.split("right:", 1)[1].strip()
                return make_call("config_diff", {"left": left, "right": right})

        if "日志" in last_user and ("分析" in last_user or "统计" in last_user):
            return make_call("log_analysis", {"log": last_user})

        if ("设备" in last_user or "主机" in last_user) and ("状态" in last_user or "可达" in last_user or "ping" in last_user.lower()) and m:
            ip = m.group("ip") or m.group("ipv6")
            return make_call("device_status", {"host": ip})

        return emit(
            LLMResponse(
                content="我可以进行路由查询、路径计算、配置对比、设备状态检查、日志分析。请直接描述需求并提供必要输入。",
                tool_calls=[],
            )
        )


__all__ = ["StaticTextChatModel", "RuleBasedChatModel"]

