from __future__ import annotations

"""Agent 消息构建模块。

把 `Agent._build_llm_messages` 的职责下沉到此处，便于：
- Manager 决策/Final merge 复用同一套“消息规范化与附件注入”规则
- 后续 Workspace/RAG/Trace 插入上下文时有单一入口
"""

import json
import logging
import os
import re
from typing import Any

from oclaw.platform.llm.chat_models import _normalize_image_b64_payload, gemini_openai_compat_client, ChatModel
from oclaw.runtime.chat.tool_runtime import tool_llm_message_max_chars, truncate_tool_result_for_llm_messages
from oclaw.prompts import render_prompt
from oclaw.platform.files.attachment_assets import attachment_id_to_data_url
from oclaw.runtime.relay_pointer import parse_pointer_uri

logger = logging.getLogger(__name__)
_THINK_BLOCK_RE = re.compile(r"<think>\s*(.*?)\s*</think>\s*", flags=re.IGNORECASE | re.DOTALL)


def _replay_recent_tool_rounds() -> int:
    raw = str(os.getenv("AIA_REPLAY_TOOL_FULL_ROUNDS") or "").strip()
    if raw.isdigit():
        return max(0, min(int(raw), 12))
    return 3


def _allow_reasoning_signature_replay(model: ChatModel) -> bool:
    # - auto (default): only providers that require signature continuity (Gemini paths).
    # - on: always include signature metadata on assistant tool_calls.
    # - off: never include signature metadata.
    policy = str(os.getenv("AIA_REPLAY_REASONING_SIGNATURE_POLICY") or "auto").strip().lower()
    if policy in ("0", "off", "false", "no"):
        return False
    if policy in ("1", "on", "true", "yes"):
        return True
    if gemini_openai_compat_client(model):
        return True
    return model.__class__.__name__ == "GoogleGeminiChatModel"


def _strip_reasoning_blocks(text: str) -> str:
    return _THINK_BLOCK_RE.sub("", str(text or "")).strip()


def _parse_tool_calls(raw_tc: Any) -> list[dict[str, Any]]:
    if not raw_tc:
        return []
    try:
        data = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _tool_call_id_from_tool_row(raw_tc: Any) -> str:
    if not raw_tc:
        return ""
    try:
        meta = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
    except Exception:
        return ""
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("tool_call_id") or "").strip()


def _collect_historical_tool_call_ids(store_messages: list[Any], *, full_rounds: int) -> set[str]:
    if full_rounds < 0:
        full_rounds = 0
    full_ids: set[str] = set()
    rounds = 0
    for m in reversed(store_messages or []):
        role = str(getattr(m, "role", "") or "")
        if role != "assistant":
            continue
        tcs = _parse_tool_calls(getattr(m, "tool_calls", None))
        tc_ids = [str(tc.get("id") or "").strip() for tc in tcs if str(tc.get("id") or "").strip()]
        if not tc_ids:
            continue
        rounds += 1
        if rounds <= full_rounds:
            full_ids.update(tc_ids)
    historical_ids: set[str] = set()
    for m in store_messages or []:
        if str(getattr(m, "role", "") or "") != "tool":
            continue
        tcid = _tool_call_id_from_tool_row(getattr(m, "tool_calls", None))
        if tcid and tcid not in full_ids:
            historical_ids.add(tcid)
    return historical_ids


def _summarize_historical_tool_content(raw: str, *, cap: int) -> str:
    s = str(raw or "").strip()
    if not s:
        return json.dumps({"ok": None, "summary": "", "_history_summarized": True}, ensure_ascii=False)
    out: dict[str, Any] = {"_history_summarized": True}
    try:
        obj = json.loads(s)
    except Exception:
        preview = s[: max(1, cap - 120)] + ("\n...<truncated>" if len(s) > cap else "")
        out["summary"] = preview
        return json.dumps(out, ensure_ascii=False)
    if not isinstance(obj, dict):
        out["summary"] = s[: max(1, cap - 120)] + ("\n...<truncated>" if len(s) > cap else "")
        return json.dumps(out, ensure_ascii=False)
    out["ok"] = obj.get("ok")
    for key in ("error_code", "error", "hint"):
        v = str(obj.get(key) or "").strip()
        if v:
            out[key] = v
    if "result" in obj:
        r = obj.get("result")
        if isinstance(r, dict):
            out["result_keys"] = sorted(list(r.keys()))[:20]
    preview = s[: max(1, cap - 260)] + ("\n...<truncated>" if len(s) > cap else "")
    out["preview"] = preview
    return json.dumps(out, ensure_ascii=False)


def _summarize_unpaired_tool_content(raw: str, *, cap: int) -> str:
    """Best-effort summarize tool JSON for model-friendly context."""
    s = str(raw or "").strip()
    if not s:
        return ""
    if cap > 0 and len(s) > cap:
        s = s[: max(1, cap - 80)] + "\n...<truncated>"
    try:
        obj = json.loads(s)
    except Exception:
        return s
    if not isinstance(obj, dict):
        return s
    lines: list[str] = []
    ok = obj.get("ok")
    if ok is not None:
        lines.append(f"ok={bool(ok)}")
    ec = str(obj.get("error_code") or "").strip()
    if ec:
        lines.append(f"error_code={ec}")
    err = str(obj.get("error") or "").strip()
    if err:
        lines.append(f"error={err}")
    hint = str(obj.get("hint") or "").strip()
    if hint:
        lines.append(f"hint={hint}")
    # Extract MCP-style text blocks when present.
    try:
        nested = obj.get("result")
        content = None
        if isinstance(nested, dict):
            content = nested.get("content")
        if isinstance(content, list):
            texts = []
            for b in content:
                if isinstance(b, dict) and str(b.get("type") or "").strip().lower() == "text":
                    t = str(b.get("text") or "").strip()
                    if t:
                        texts.append(t)
            if texts:
                lines.append("content_text=" + " | ".join(texts)[: min(800, cap)])
    except Exception:
        pass
    head = " ".join(lines).strip()
    if head:
        return head + "\n" + s
    return s


def build_llm_messages(
    *,
    store_messages: list[Any],
    system_prompt: str,
    model: ChatModel,
    lang: str,
) -> list[dict[str, Any]]:
    """把 DB 中的消息序列转换为 LLM messages。"""
    out: list[dict[str, Any]] = [{"role": "system", "content": (system_prompt or "").strip()}]
    allow_signature_replay = _allow_reasoning_signature_replay(model)
    historical_tool_ids = _collect_historical_tool_call_ids(
        store_messages=store_messages, full_rounds=_replay_recent_tool_rounds()
    )
    # Some OpenAI-compatible gateways error if a tool message references a tool_call_id
    # that is not present in the assistant tool_calls within the same request context.
    # This can happen when context windows are trimmed and the assistant tool_calls row is dropped.
    valid_tool_call_ids: set[str] = set()
    for m in store_messages:
        role = str(getattr(m, "role", "") or "")
        event_type = str(getattr(m, "event_type", "") or "").strip().lower()
        if event_type == "reasoning":
            continue

        if role == "user":
            content_list: list[dict[str, Any]] = []
            text = getattr(m, "content", None)
            if text:
                content_list.append({"type": "text", "text": str(text)})

            attachments = []
            raw_att = getattr(m, "attachments", None)
            if raw_att:
                try:
                    attachments = json.loads(raw_att) if isinstance(raw_att, str) else raw_att
                except Exception:
                    attachments = []

            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                att_type = att.get("type")
                if att_type in ("image", "input_image"):
                    b64 = _normalize_image_b64_payload(att.get("image_base64") or att.get("data"))
                    if not b64:
                        continue
                    content_list.append(
                        {
                            "type": "input_image",
                            "image_base64": b64,
                            "mime": att.get("mime") or "image/jpeg",
                        }
                    )
                elif att_type == "image_ref":
                    # Prefer actual image bytes so multi-agent/image specialist can truly "see" history images.
                    name = str(att.get("name") or "image")
                    mime = str(att.get("mime") or "image/jpeg")
                    aid = str(att.get("attachment_id") or "")
                    data_url = attachment_id_to_data_url(aid, mime=mime) if aid else ""
                    if data_url:
                        if ";base64," in data_url:
                            b64 = data_url.split(";base64,", 1)[1]
                            content_list.append(
                                {
                                    "type": "input_image",
                                    "image_base64": b64,
                                    "mime": mime,
                                }
                            )
                            continue
                    w = att.get("width")
                    h = att.get("height")
                    sz = att.get("bytes")
                    meta_line = f"- name={name} mime={mime} id={aid}"
                    if w and h:
                        meta_line += f" size={w}x{h}"
                    if sz:
                        meta_line += f" bytes={sz}"
                    content_list.append(
                        {
                            "type": "text",
                            "text": render_prompt(
                                "tools/image_attachment_meta.md",
                                variables={"meta_line": meta_line},
                                strict=True,
                            ),
                        }
                    )
                elif att_type == "text":
                    name = att.get("name", "file")
                    text_content = att.get("content", "")
                    content_list.append(
                        {
                            "type": "text",
                            "text": render_prompt(
                                "tools/text_attachment_wrap.md",
                                variables={"name": str(name), "content": str(text_content)},
                                strict=True,
                            ),
                        }
                    )
                elif att_type == "tabular_ref":
                    name = str(att.get("name") or "table")
                    table_id = str(att.get("table_id") or "")
                    rows = int(att.get("rows") or 0)
                    cols = int(att.get("cols") or 0)
                    aid = str(att.get("attachment_id") or "")
                    sheets = att.get("sheets") if isinstance(att.get("sheets"), list) else []
                    sheet_hint = ""
                    if sheets:
                        names = [str((x or {}).get("sheet_name") or "") for x in sheets if isinstance(x, dict)]
                        names = [x for x in names if x]
                        if names:
                            sheet_hint = f"\n- sheets: {', '.join(names[:8])}"
                    content_list.append(
                        {
                            "type": "text",
                            "text": (
                                f"[LargeTableAttachment]\n"
                                f"- name: {name}\n"
                                f"- table_id: {table_id}\n"
                                f"- attachment_id: {aid}\n"
                                f"- rows: {rows}\n"
                                f"- cols: {cols}\n"
                                f"{sheet_hint}\n"
                                f"- tools: query_tabular_attachment, run_tabular_sql, analyze_tabular_attachment_full_scan"
                            ),
                        }
                    )
                elif att_type == "relay_pointer":
                    p_uri = str(att.get("pointer_uri") or "").strip()
                    if not p_uri:
                        continue
                    mime = str(att.get("mime") or att.get("mime_type") or "").strip()
                    aid = str(att.get("attachment_id") or "").strip()
                    if (not aid) and p_uri:
                        try:
                            _scope, _fid = parse_pointer_uri(p_uri)
                            aid = str(_fid or "").strip()
                        except Exception:
                            aid = ""
                    if aid and mime.startswith("image/"):
                        data_url = attachment_id_to_data_url(aid, mime=mime)
                        if data_url and ";base64," in data_url:
                            b64 = data_url.split(";base64,", 1)[1]
                            content_list.append(
                                {
                                    "type": "input_image",
                                    "image_base64": b64,
                                    "mime": mime or "image/jpeg",
                                }
                            )
                    rel_path = str(att.get("rel_path") or "").strip()
                    sz = att.get("bytes")
                    sha = str(att.get("sha256") or "").strip()
                    pointer_line = f"- pointer_uri={p_uri}"
                    if rel_path:
                        pointer_line += f" rel_path={rel_path}"
                    if mime:
                        pointer_line += f" mime={mime}"
                    if sz:
                        pointer_line += f" bytes={sz}"
                    if sha:
                        pointer_line += f" sha256={sha}"
                    content_list.append({"type": "text", "text": pointer_line})

            if not content_list:
                placeholder = "(No text content)" if str(lang or "").startswith("en") else "（无文本内容）"
                content_list.append({"type": "text", "text": placeholder})

            if len(content_list) == 1 and content_list[0].get("type") == "text":
                out.append({"role": "user", "content": content_list[0]["text"]})
            else:
                out.append({"role": "user", "content": content_list})
            continue

        if role == "assistant":
            tool_calls = None
            raw_tc = getattr(m, "tool_calls", None)
            if raw_tc:
                try:
                    tool_calls = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
                except Exception:
                    tool_calls = None

            if tool_calls and isinstance(tool_calls, list):
                api_tool_calls = []
                gemini_fc = gemini_openai_compat_client(model)
                for idx, tc in enumerate(tool_calls):
                    if not isinstance(tc, dict) or not tc.get("id") or not tc.get("name"):
                        continue
                    try:
                        valid_tool_call_ids.add(str(tc.get("id") or ""))
                    except Exception:
                        pass
                    entry: dict[str, Any] = {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                        },
                    }
                    raw_sig = tc.get("thought_signature")
                    if allow_signature_replay and gemini_fc:
                        if isinstance(raw_sig, str):
                            sig = raw_sig
                        elif idx == 0:
                            sig = "skip_thought_signature_validator"
                        else:
                            sig = ""
                        entry["extra_content"] = {"google": {"thought_signature": sig}}
                    elif allow_signature_replay and isinstance(raw_sig, str):
                        entry["extra_content"] = {"google": {"thought_signature": raw_sig}}
                    api_tool_calls.append(entry)
                if api_tool_calls:
                    out.append(
                        {
                            "role": "assistant",
                            "content": _strip_reasoning_blocks(getattr(m, "content", "") or ""),
                            "tool_calls": api_tool_calls,
                        }
                    )
                else:
                    out.append({"role": "assistant", "content": _strip_reasoning_blocks(getattr(m, "content", "") or "")})
            else:
                out.append({"role": "assistant", "content": _strip_reasoning_blocks(getattr(m, "content", "") or "")})
            continue

        if role == "tool":
            tool_call_id = None
            raw_tc = getattr(m, "tool_calls", None)
            if raw_tc:
                try:
                    meta = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
                    if isinstance(meta, dict):
                        tool_call_id = meta.get("tool_call_id")
                except Exception:
                    tool_call_id = None
            if tool_call_id is not None:
                try:
                    tool_call_id = str(tool_call_id).strip()
                except Exception:
                    tool_call_id = ""
            if tool_call_id:
                # Guard against dangling tool_call_id (assistant tool_calls missing from this trimmed context window).
                if str(tool_call_id) not in valid_tool_call_ids:
                    # Preserve tool evidence, but downgrade to plain assistant text when pairing is broken.
                    # Some OpenAI-compatible gateways reject a role=tool message if tool_call_id cannot be paired
                    # to an assistant.tool_calls.id within the same request context.
                    r0 = getattr(m, "content", "") or ""
                    cap0 = tool_llm_message_max_chars()
                    pretty = _summarize_unpaired_tool_content(r0, cap=cap0)
                    out.append(
                        {
                            "role": "assistant",
                            "content": render_prompt(
                                "tools/tool_result_unpaired.md",
                                variables={"tag": "tool_use_result:unpaired", "payload": pretty},
                                strict=True,
                            ),
                        }
                    )
                    continue
                raw_tc_content = getattr(m, "content", "") or ""
                tool_content_out = raw_tc_content
                cap = tool_llm_message_max_chars()
                if str(tool_call_id) in historical_tool_ids:
                    summary_cap = 1800
                    if cap > 0:
                        summary_cap = max(600, min(2400, cap // 3))
                    tool_content_out = _summarize_historical_tool_content(raw_tc_content, cap=summary_cap)
                elif cap > 0 and len(raw_tc_content) > cap:
                    try:
                        parsed = json.loads(raw_tc_content)
                        if isinstance(parsed, dict):
                            tool_content_out = json.dumps(
                                truncate_tool_result_for_llm_messages(parsed), ensure_ascii=False, default=str
                            )
                        else:
                            tool_content_out = raw_tc_content[: max(1, cap - 80)] + "\n...<truncated>"
                    except Exception:
                        tool_content_out = raw_tc_content[: max(1, cap - 80)] + "\n...<truncated>"
                tool_row: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_content_out,
                }
                # Some OpenAI-compatible gateways expect `call_id` instead of `tool_call_id`.
                # Sending both (non-empty) keeps compatibility; servers should ignore unknown fields.
                tool_row["call_id"] = tool_call_id
                try:
                    meta2 = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
                except Exception:
                    meta2 = None
                if isinstance(meta2, dict) and meta2.get("name"):
                    tool_row["name"] = str(meta2["name"])
                out.append(tool_row)
            else:
                r = getattr(m, "content", "") or ""
                cap2 = tool_llm_message_max_chars()
                pretty2 = _summarize_unpaired_tool_content(r, cap=cap2)
                out.append(
                    {
                        "role": "assistant",
                        "content": render_prompt(
                            "tools/tool_result_unpaired.md",
                            variables={"tag": "tool_use_result:no_id", "payload": pretty2},
                            strict=True,
                        ),
                    }
                )
            continue

    return out


__all__ = ["build_llm_messages"]
