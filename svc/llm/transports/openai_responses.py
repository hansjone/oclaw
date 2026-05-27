from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from typing import Any, Optional
from collections.abc import Callable, Iterable

from svc.llm.transports.base import ChatModel, LLMResponse, LLMToolCall, normalize_image_b64_payload
from runtime.dsml_tool_parse import promote_dsml_tool_calls_in_response, should_recover_dsml_tool_calls

logger = logging.getLogger(__name__)


def _redact_nested_json_preview(obj: Any, *, max_chars: int = 4000) -> str:
    """Best-effort JSON preview for logs (truncate; redact mega data URLs)."""

    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)

    def _clip_data_urls(t: str) -> str:
        out_parts: list[str] = []
        i = 0
        needle = "data:"
        while i < len(t):
            j = t.find(needle, i)
            if j < 0:
                out_parts.append(t[i:])
                break
            out_parts.append(t[i:j])
            k = j + len(needle)
            while k < len(t) and t[k] not in "?;, \n\r\t\"]":
                k += 1
            if k < len(t) and t[k:k + 8] == ";base64,":
                end = k + 8
                while end < len(t) and t[end] not in "\"}] \n\r\t":
                    end += 1
                seg = end - (k + 8)
                out_parts.append(f"data:<redacted base64 ~{seg} chars>")
                i = end
                continue
            out_parts.append(t[j:k])
            i = k
        return "".join(out_parts)

    s = _clip_data_urls(s)
    if len(s) > max_chars:
        return s[: max_chars - 40] + "\n...<<truncated>>\n..."
    return s


def _deep_redact_for_debug(obj: Any) -> Any:
    """Recursive copy for logs: shorten giant ``data:...;base64,...`` and very long strings."""

    if isinstance(obj, dict):
        return {str(k): _deep_redact_for_debug(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_redact_for_debug(x) for x in obj]
    if isinstance(obj, str):
        s = obj
        if ";base64," in s and s.strip().startswith("data:") and len(s) > 160:
            head, _, _tail = s.partition(";base64,")
            return f"{head};base64,<redacted ~{len(s) - len(head) - 8} b64 chars>"
        if len(s) > 16_000:
            return s[:12_000] + f"...<truncated {len(s) - 12_000} chars>"
        return s
    return obj


def _safe_int(raw: str | None, default: int, *, max_value: int = 2_000_000) -> int:
    try:
        value = int(str(raw or "").strip())
    except Exception:
        return default
    if value < 1:
        return default
    return min(value, max_value)


def _log_openai_responses_wire_kwargs(payload: dict[str, Any], *, variant: str, phase: str) -> None:
    """Temporary diagnostics: log kwargs passed into ``OpenAI.responses.create`` (after our assembly).

    Enable: ``AIA_RESPONSES_DEBUG_PRINT_PAYLOAD=1`` — emits ``logging.warning`` **and** the same JSON on **stderr**
    (gateway控制台默认可见，不依赖 logging level)。

    Notes:

    - OpenAI SDK may still apply minor JSON transforms on send; this matches **our** arguments.
    - Base64 / long ``data:`` URLs are redacted to keep logs readable.
    """
    raw = str(os.getenv("AIA_RESPONSES_DEBUG_PRINT_PAYLOAD") or "").strip().lower()
    if raw not in ("1", "true", "yes", "on"):
        return
    try:
        dbg = _deep_redact_for_debug(dict(payload))
        txt = json.dumps(dbg, ensure_ascii=False, indent=2, default=str)
        cap = _safe_int(os.getenv("AIA_RESPONSES_DEBUG_PRINT_MAX_CHARS"), 120_000, max_value=500_000)
        if len(txt) > cap:
            txt = txt[: max(cap - 80, 0)] + "\n...<<truncated>>\n"
        logger.warning(
            "openai_responses DEBUG wire kwargs [%s] variant=%s (%d chars):\n%s",
            phase,
            variant,
            len(txt),
            txt,
        )
        try:
            sys.stderr.write(
                f"\n[oclaw openai_responses DEBUG] phase={phase} variant={variant} chars={len(txt)}\n{txt}\n\n"
            )
            sys.stderr.flush()
        except Exception:
            pass
    except Exception as exc:
        logger.warning("openai_responses DEBUG payload serialization failed: %s", exc)


def _openai_sdk_diagnostic_text(exc: BaseException) -> str:
    """``str(APIStatusError)`` is often only ``Error code: 400``; validation detail lives in ``body['message']``."""
    chunks: list[str] = [str(exc)]
    msg = getattr(exc, "message", None)
    if isinstance(msg, str) and msg.strip() and msg not in chunks:
        chunks.append(msg)
    bod = getattr(exc, "body", None)
    if isinstance(bod, dict):
        bm = bod.get("message")
        if isinstance(bm, str) and bm.strip():
            chunks.append(bm)
        err = bod.get("error")
        if isinstance(err, dict):
            em = err.get("message")
            if isinstance(em, str) and em.strip():
                chunks.append(em)
    return "\n".join(chunks)


def _is_input_messages_validation_error(exc: BaseException) -> bool:
    """Third-party gateways often return 400/422 with Pydantic paths like ``input.messages.0.role``."""
    m = _openai_sdk_diagnostic_text(exc).lower()
    if "input.messages" in m:
        return True
    if "input should be 'user'" in m and "content" in m:
        return True
    return False


def _as_dict(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            d = obj.model_dump(mode="python")
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


def _collect_tool_calls_from_response_dict(resp: dict[str, Any]) -> list[LLMToolCall]:
    out: list[LLMToolCall] = []
    items = resp.get("output")
    if not isinstance(items, list):
        return out
    for it in items:
        d = _as_dict(it)
        if not d:
            continue
        if str(d.get("type") or "") in ("function_call", "tool_call"):
            call_id = str(d.get("call_id") or d.get("id") or "") or f"call_{uuid.uuid4().hex}"
            name = str(d.get("name") or "") or str((d.get("function") or {}).get("name") or "")
            args = d.get("arguments") or d.get("input") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"_raw": args}
            if not isinstance(args, dict):
                args = {"_raw": args}
            out.append(LLMToolCall(id=call_id, name=name, arguments=args, thought_signature=None))
    return out


def _stream_reasoning_delta_text(ev: dict[str, Any]) -> str:
    """Extract a textual chunk from a Responses streaming reasoning-related event."""
    delta = ev.get("delta")
    if isinstance(delta, dict):
        for k in ("text", "delta", "summary", "content"):
            v = delta.get(k)
            if isinstance(v, str) and v:
                return v
        return ""
    if delta is not None:
        s = str(delta)
        return s
    for k in ("text", "summary", "content"):
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _reasoning_from_completed_response(resp: dict[str, Any]) -> str:
    """Best-effort reasoning string from a terminal Responses ``response`` object."""
    for key in ("reasoning", "reasoning_summary", "reasoning_text", "reasoning_content"):
        v = resp.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    items = resp.get("output")
    if not isinstance(items, list):
        return ""
    chunks: list[str] = []
    for it in items:
        d = _as_dict(it) or {}
        typ = str(d.get("type") or "").lower()
        if "reasoning" not in typ:
            continue
        for k in ("summary", "text", "content"):
            x = d.get(k)
            if isinstance(x, str) and x.strip():
                chunks.append(x.strip())
                break
    return "\n".join(chunks).strip()


def parse_openai_responses_stream_events(
    events: Iterable[Any],
    *,
    on_token: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[LLMToolCall], dict[str, Any] | None, str]:
    """Pure stream parser (offline-testable).

    Returns: (assembled_output_text, tool_calls, final_response_dict?, reasoning_text)

    Reasoning models emit ``response.reasoning_summary_text.delta`` (and similar) events; those are
    forwarded to ``on_token`` for live UI, accumulated into ``reasoning_text`` for persistence, and
    are **not** merged into the returned ``assembled_output_text`` (assistant body).
    """
    parts: list[str] = []
    reasoning_parts: list[str] = []
    final_resp: dict[str, Any] | None = None

    def _emit_reasoning_chunk(s: str) -> None:
        s = str(s or "")
        if not s:
            return
        reasoning_parts.append(s)
        if on_token:
            on_token(s)

    for ev in events:
        d = _as_dict(ev) or {}
        typ = str(d.get("type") or "")
        # Reasoning / thinking summary stream (do not append to output_text body).
        if typ in (
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text",
            "response.reasoning_text.delta",
            "response.reasoning_text",
            "response.reasoning_summary.delta",
        ) or (typ.startswith("response.reasoning") and typ.endswith(".delta")):
            rs = _stream_reasoning_delta_text(d)
            if rs:
                _emit_reasoning_chunk(rs)
            continue
        # Text deltas
        if typ in ("response.output_text.delta", "response.output_text"):
            delta = d.get("delta")
            if delta is None:
                delta = d.get("text")
            s = str(delta or "")
            if s:
                parts.append(s)
                if on_token:
                    on_token(s)
            continue
        # Sometimes the SDK emits generic `response.delta` with nested segments.
        if typ == "response.delta":
            delta = d.get("delta")
            if isinstance(delta, dict):
                txt = delta.get("output_text")
                if isinstance(txt, str) and txt:
                    parts.append(txt)
                    if on_token:
                        on_token(txt)
                for rkey in ("reasoning_summary_text", "reasoning_text", "reasoning"):
                    rv = delta.get(rkey)
                    if isinstance(rv, str) and rv:
                        _emit_reasoning_chunk(rv)
            continue
        # Terminal response object
        if typ in ("response.completed", "response.complete", "response.done"):
            resp = d.get("response") or d.get("data") or d.get("result")
            final_resp = _as_dict(resp) or final_resp
            continue
        if typ == "response.created":
            continue
        # Some SDK versions yield the response object directly (no explicit event type).
        if d.get("output") is not None and d.get("id") is not None:
            final_resp = d

    text = "".join(parts)
    tool_calls = _collect_tool_calls_from_response_dict(final_resp) if final_resp else []
    reasoning_text = "".join(reasoning_parts).strip()
    if not reasoning_text and final_resp:
        reasoning_text = _reasoning_from_completed_response(final_resp)
    return text, tool_calls, final_resp, reasoning_text


class OpenAIResponsesModel(ChatModel):
    """OpenAI Responses API transport (OpenAI-compatible gateways may implement this surface)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking_mode_enabled: bool = False,
        reasoning_effort: str | None = None,
    ):
        self.model = (model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "").strip() or None
        self.thinking_mode_enabled = bool(thinking_mode_enabled)
        eff = str(reasoning_effort or "").strip().lower()
        self.reasoning_effort = eff if eff in ("low", "medium", "high") else ""
        if not self.api_key:
            raise RuntimeError("未设置 OPENAI_API_KEY，无法使用 OpenAI Responses")
        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError("未安装 openai 依赖，请先 pip install -r requirements.txt") from e
        kw: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kw["base_url"] = self.base_url
        self._client = OpenAI(**kw)

    def _finalize_response(self, content: str, tool_calls: list[LLMToolCall], reasoning: str) -> LLMResponse:
        text = str(content or "")
        reasoning_text = str(reasoning or "")
        calls = list(tool_calls or [])
        if should_recover_dsml_tool_calls(
            model_id=str(self.model or ""),
            base_url=str(self.base_url or ""),
            thinking_mode_enabled=bool(getattr(self, "thinking_mode_enabled", False)),
        ):
            text, reasoning_text, calls = promote_dsml_tool_calls_in_response(text, reasoning_text, calls)
        return LLMResponse(content=text, tool_calls=calls, reasoning_content=reasoning_text.strip())

    @staticmethod
    def _strip_leading_system_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Separate leading ``role=system`` rows for ``instructions=` (Responses API expects user-shaped ``input.messages``)."""
        msgs = messages or []
        sys_chunks: list[str] = []
        i = 0
        while i < len(msgs):
            m = msgs[i]
            if not isinstance(m, dict):
                break
            if str(m.get("role") or "").strip().lower() != "system":
                break
            c = m.get("content")
            if isinstance(c, str) and c.strip():
                sys_chunks.append(c.strip())
            elif isinstance(c, list):
                texts: list[str] = []
                for it in c:
                    if not isinstance(it, dict):
                        continue
                    tt = str(it.get("type") or "").strip().lower()
                    if tt in ("text", "input_text"):
                        xs = str(it.get("text") or "").strip()
                        if xs:
                            texts.append(xs)
                    elif isinstance(it.get("text"), str) and str(it.get("text")).strip():
                        texts.append(str(it.get("text")).strip())
                if texts:
                    sys_chunks.append("\n".join(texts))
            i += 1
        joined = "\n\n".join(sys_chunks).strip()
        return joined, list(msgs[i:])

    @staticmethod
    def _normalize_messages(
        messages: list[dict[str, Any]],
        *,
        envelope_openai_message: bool = True,
        content_chat_completions_parts: bool = False,
        image_detail_auto: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Build Response input rows used under ``input`` (flat array) or ``input.messages``.

        - **Responses content** (default when ``content_chat_completions_parts=False``): each part is
          ``{"type":"input_text",...}`` / ``{"type":"input_image","image_url":"<str>","detail":"auto"}``
          (`OpenAI response_input_*` TypedDict surface).
        - **Chat completions content** (``content_chat_completions_parts=True``): ``text`` /
          ``image_url`` multimodal blocks.
        - **Envelope** ``envelope_openai_message=True``: ``{"type":"message","role","content":[...]}``;
          ``False``: ``{"role","content":[...]}`` (per some Bailian curls).
        """
        out: list[dict[str, Any]] = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "user").strip().lower() or "user"
            content = m.get("content")
            norm_content: list[dict[str, Any]] = []

            def _append_image_part(url_value: str) -> None:
                if content_chat_completions_parts:
                    norm_content.append({"type": "image_url", "image_url": {"url": url_value}})
                else:
                    p: dict[str, Any] = {"type": "input_image", "image_url": url_value}
                    if image_detail_auto:
                        p["detail"] = "auto"
                    norm_content.append(p)

            def _append_text_part(txt: str) -> None:
                if content_chat_completions_parts:
                    norm_content.append({"type": "text", "text": txt})
                else:
                    norm_content.append({"type": "input_text", "text": txt})

            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "input_image":
                        mime = str(item.get("mime") or "image/jpeg").strip() or "image/jpeg"
                        b64 = normalize_image_b64_payload(item.get("image_base64") or item.get("data"))
                        if not b64:
                            continue
                        _append_image_part(f"data:{mime};base64,{b64}")
                        continue
                    if isinstance(item, dict) and str(item.get("type") or "").strip().lower() == "image_url":
                        iu = item.get("image_url")
                        url = ""
                        if isinstance(iu, dict):
                            url = str(iu.get("url") or "").strip()
                        elif isinstance(iu, str):
                            url = iu.strip()
                        if url.startswith(("http://", "https://", "data:")):
                            _append_image_part(url)
                        continue
                    if isinstance(item, dict) and item.get("type") in ("input_text", "text"):
                        t = str(item.get("text") or "").strip()
                        if t:
                            _append_text_part(t)
                        continue
                    if isinstance(item, dict):
                        itype = str(item.get("type") or "").strip().lower()
                        img_key = item.get("image")
                        if isinstance(img_key, str) and img_key.strip() and itype != "input_image":
                            uu = img_key.strip()
                            if uu.startswith(("http://", "https://", "data:")):
                                _append_image_part(uu)
                                continue
                        if isinstance(item.get("text"), str) and str(item.get("text") or "").strip():
                            _append_text_part(str(item.get("text") or "").strip())
                            continue
                        s = str(item.get("text") or "").strip()
                        if s:
                            _append_text_part(s)
                        continue
                    s = str(item or "").strip()
                    if s:
                        _append_text_part(s)
            elif isinstance(content, str):
                txt = content.strip()
                if txt:
                    _append_text_part(txt)
            elif content is not None:
                s = str(content).strip()
                if s:
                    _append_text_part(s)

            if not norm_content:
                continue

            coerced_role = "user"
            if role != "user":
                prefix = "assistant" if role == "assistant" else ("system" if role == "system" else role)
                norm_content.insert(
                    0,
                    OpenAIResponsesModel._role_prefix_part(prefix, content_chat_completions_parts),
                )

            if envelope_openai_message:
                out.append({"type": "message", "role": coerced_role, "content": norm_content})
            else:
                out.append({"role": coerced_role, "content": norm_content})
        return out

    @staticmethod
    def _role_prefix_part(prefix: str, chat_parts: bool) -> dict[str, Any]:
        t = f"[{prefix}]"
        if chat_parts:
            return {"type": "text", "text": t}
        return {"type": "input_text", "text": t}

    @staticmethod
    def _responses_input_candidates(
        msgs: list[dict[str, Any]],
        *,
        flat_responses: bool,
        prefer_envelope: bool,
        prefer_chat_parts: bool,
    ) -> list[tuple[str, Any]]:
        """Several gateways validate ``input.messages`` differently; try a small deterministic set."""

        def N(env: bool, chat: bool) -> list[dict[str, Any]]:
            return OpenAIResponsesModel._normalize_messages(
                msgs,
                envelope_openai_message=env,
                content_chat_completions_parts=chat,
            )

        keys_seen: set[str] = set()
        out: list[tuple[str, Any]] = []

        def push(tag: str, inp: Any) -> None:
            try:
                sk = json.dumps(inp, ensure_ascii=False, sort_keys=True, default=str)
            except Exception:
                sk = repr(inp)
            if sk in keys_seen:
                return
            keys_seen.add(sk)
            out.append((tag, inp))

        if flat_responses:
            for env in (prefer_envelope, not prefer_envelope):
                push(f"flat_envelope_{env}", N(env, False))
            return out

        # Prefer profile/env defaults first (``AIA_RESPONSES_NESTED_CHAT_PARTS`` / envelope toggles), then a fixed
        # fallback ring so picky gateways still get Chat-shaped ``input.messages`` without dropping multimodal pixels.
        primary_combo = (prefer_envelope, prefer_chat_parts)
        fallback_ring = [(False, True), (False, False), (True, False), (True, True)]
        combos = [primary_combo] + [p for p in fallback_ring if p != primary_combo]
        for env, chat in combos:
            norm = N(env, chat)
            push(f"e{int(env)}c{int(chat)}_messages", {"messages": norm})
            push(f"e{int(env)}c{int(chat)}_flat_input", norm)
        return out

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        sys_instructions, rest = OpenAIResponsesModel._strip_leading_system_messages(messages)
        def _env_truthy(name: str) -> bool:
            return str(os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")

        if _env_truthy("AIA_RESPONSES_DEBUG_PRINT_PAYLOAD"):
            try:
                sys.stderr.write(
                    "[oclaw openai_responses] chat() ENTERED "
                    f"model={self.model!r} base_url={self.base_url!r} "
                    f"messages={len(messages)} tools={len(tools or [])}\n"
                )
                sys.stderr.flush()
            except Exception:
                pass

        # Default: nested ``input.messages`` rows use **Responses** parts (``input_text`` / ``input_image``).
        # Flat Bailian ``input`` array: ``AIA_RESPONSES_INPUT_IS_FLAT_LIST=1`` (optional ``AIA_RESPONSES_FLAT_OPENAI_ENVELOPE``).
        flat_raw = os.getenv("AIA_RESPONSES_INPUT_IS_FLAT_LIST")
        if flat_raw is not None and str(flat_raw).strip():
            flat_responses = _env_truthy("AIA_RESPONSES_INPUT_IS_FLAT_LIST")
        else:
            legacy = os.getenv("AIA_RESPONSES_INPUT_USE_MESSAGES_ARRAY")
            if legacy is None or not str(legacy).strip():
                flat_responses = False
            else:
                flat_responses = not _env_truthy("AIA_RESPONSES_INPUT_USE_MESSAGES_ARRAY")

        # Nested ``input.messages`` defaults to **Responses** content parts (``input_*``) + ``type:message``,
        # matching OpenAI ``EasyInputMessageParam`` / Model Studio expanded examples. Some proxies wrongly
        # expect Chat ``text``/``image_url`` parts → ``AIA_RESPONSES_NESTED_CHAT_PARTS=1``.
        if flat_responses:
            envelope_openai_message = _env_truthy("AIA_RESPONSES_FLAT_OPENAI_ENVELOPE")
            nested_chat_parts = False
        else:
            envelope_openai_message = True
            nested_chat_parts = _env_truthy("AIA_RESPONSES_NESTED_CHAT_PARTS")

        def _normalize_batch(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return OpenAIResponsesModel._normalize_messages(
                msgs,
                envelope_openai_message=envelope_openai_message,
                content_chat_completions_parts=nested_chat_parts,
            )

        msgs_for_norm: list[dict[str, Any]]
        if rest:
            msgs_for_norm = rest
            norm = _normalize_batch(rest)
            inst_kw: dict[str, Any] = {}
            if sys_instructions.strip():
                si = sys_instructions.strip()
                if len(si) > 80_000:
                    si = si[:80_000] + "\n...[truncated]"
                inst_kw = {"instructions": si}
            if not norm:
                msgs_for_norm = messages
                norm = _normalize_batch(messages)
                inst_kw = {}
        else:
            msgs_for_norm = messages
            norm = _normalize_batch(messages)
            inst_kw = {}

        explicit_variants = os.getenv("AIA_RESPONSES_INPUT_VARIANTS")
        bu_norm = (self.base_url or "").strip().lower()
        # CRITICAL: do **not** treat empty ``base_url`` as "official" here. Clients often omit storing the
        # default URL in profiles while still hitting third-party gateways via env/SDK defaults—but then we
        # would wrongly disable alternate ``input`` shapes and only ever send ``primary``.
        host_is_explicit_official_api = bool(bu_norm) and ("api.openai.com" in bu_norm)
        if explicit_variants is not None and str(explicit_variants).strip():
            multi_shape = _env_truthy("AIA_RESPONSES_INPUT_VARIANTS")
        else:
            multi_shape = not host_is_explicit_official_api

        if flat_responses:
            primary_input: Any = norm
        else:
            primary_input = {"messages": norm}

        input_candidates: list[tuple[str, Any]]
        if multi_shape and not _env_truthy("AIA_RESPONSES_DISABLE_INPUT_VARIANTS"):
            input_candidates = OpenAIResponsesModel._responses_input_candidates(
                msgs_for_norm,
                flat_responses=flat_responses,
                prefer_envelope=envelope_openai_message,
                prefer_chat_parts=nested_chat_parts,
            )
        else:
            input_candidates = [("primary", primary_input)]

        stream_errors: list[str] = []
        b = str(self.base_url or "").strip().lower()
        force_disable = str(os.getenv("AIA_LLM_THINKING_FORCE_DISABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        force_enable = str(os.getenv("AIA_LLM_THINKING_FORCE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        mode_enabled = bool(getattr(self, "thinking_mode_enabled", False))
        extra_body: dict[str, Any] = {}
        if b and ("api.openai.com" not in b):
            if force_disable:
                extra_body["thinking"] = {"type": "disabled"}
            elif force_enable or mode_enabled:
                extra_body["thinking"] = {"type": "enabled"}
            else:
                # Default: disable thinking for non-official gateways unless explicitly enabled.
                if str(os.getenv("AIA_LLM_THINKING_DISABLED") or "1").strip().lower() in ("1", "true", "yes", "on"):
                    extra_body["thinking"] = {"type": "disabled"}
        thinking = {"extra_body": extra_body} if extra_body else {}
        reasoning_effort = str(getattr(self, "reasoning_effort", "") or "").strip().lower()
        if reasoning_effort not in ("low", "medium", "high"):
            reasoning_effort = ""
        base_stream_template: dict[str, Any] = {
            **thinking,
            **inst_kw,
            **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
            "model": self.model,
            "tools": tools or None,
            "stream": True,
        }
        try:
            for cand_label, responses_input in input_candidates:
                stream_payload = {**base_stream_template, "input": responses_input}
                if _env_truthy("AIA_RESPONSES_LOG_PAYLOAD_SUMMARY"):
                    logger.warning(
                        "openai_responses [%s] payload summary (redacted): %s",
                        cand_label,
                        _redact_nested_json_preview(
                            {
                                "model": self.model,
                                "input": responses_input,
                                "has_instructions": bool(inst_kw.get("instructions")),
                                "tools_n": len(tools or []),
                                "stream": True,
                            }
                        ),
                    )
                payload = stream_payload
                _log_openai_responses_wire_kwargs(payload, variant=str(cand_label), phase="stream")
                try:
                    stream = self._client.responses.create(**payload)
                    text, tool_calls, final_resp, reasoning_text = parse_openai_responses_stream_events(
                        stream, on_token=on_token
                    )
                    if (not text.strip()) and final_resp:
                        ot = final_resp.get("output_text")
                        if isinstance(ot, str) and ot.strip():
                            text = ot
                            if on_token:
                                on_token(text)
                    if cand_label != input_candidates[0][0]:
                        logger.info("openai_responses: succeeded with input variant %s", cand_label)
                    return self._finalize_response(text, tool_calls, reasoning_text)
                except Exception as exc:
                    emsg = str(exc)
                    # Fallback: provider thinking-mode replay contract.
                    if "reasoning_content" in emsg and "thinking mode" in emsg and "must be passed back" in emsg:
                        try:
                            forced = dict(payload)
                            eb = forced.get("extra_body") if isinstance(forced.get("extra_body"), dict) else {}
                            eb = dict(eb)
                            eb["thinking"] = {"type": "disabled"}
                            forced["extra_body"] = eb
                            forced.pop("reasoning_effort", None)
                            _log_openai_responses_wire_kwargs(
                                forced,
                                variant=f"{cand_label}_thinking_disabled",
                                phase="stream_retry_thinking",
                            )
                            stream = self._client.responses.create(**forced)
                            text, tool_calls, final_resp, reasoning_text = parse_openai_responses_stream_events(
                                stream, on_token=on_token
                            )
                            if (not text.strip()) and final_resp:
                                ot = final_resp.get("output_text")
                                if isinstance(ot, str) and ot.strip():
                                    text = ot
                                    if on_token:
                                        on_token(text)
                            if cand_label != input_candidates[0][0]:
                                logger.info("openai_responses: succeeded with input variant %s", cand_label)
                            return self._finalize_response(text, tool_calls, reasoning_text)
                        except Exception:
                            pass
                    if _env_truthy("AIA_RESPONSES_LOG_API_ERROR_DETAIL"):
                        eb = getattr(exc, "body", None)
                        if eb is not None:
                            logger.warning(
                                "responses.create stream [%s] body: %s", cand_label, eb
                            )
                    if len(input_candidates) > 1 and _is_input_messages_validation_error(exc):
                        stream_errors.append(f"{cand_label}:{emsg}")
                        continue
                    stream_errors.append(emsg)
                    break
            raise RuntimeError("; ".join(stream_errors) or "responses_stream_all_variants_failed")
        except Exception as exc:
            logger.info("responses stream failed; fallback to non-stream (%s)", exc)
            nonstream_errors: list[str] = []
            base_nonstream = {
                **thinking,
                **inst_kw,
                **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
                "model": self.model,
                "tools": tools or None,
            }
            for cand_label, responses_input in input_candidates:
                payload = {**base_nonstream, "input": responses_input}
                _log_openai_responses_wire_kwargs(payload, variant=str(cand_label), phase="non_stream")
                try:
                    resp = self._client.responses.create(**payload)
                    d = _as_dict(resp) or {}
                    text = str(d.get("output_text") or "")
                    tool_calls = _collect_tool_calls_from_response_dict(d)
                    reasoning_text = _reasoning_from_completed_response(d)
                    if on_token and text:
                        on_token(text)
                    if cand_label != input_candidates[0][0]:
                        logger.info("openai_responses non-stream: succeeded with input variant %s", cand_label)
                    return self._finalize_response(text, tool_calls, reasoning_text)
                except Exception as e2:
                    emsg2 = str(e2)
                    if "reasoning_content" in emsg2 and "thinking mode" in emsg2 and "must be passed back" in emsg2:
                        try:
                            forced = dict(payload)
                            eb = forced.get("extra_body") if isinstance(forced.get("extra_body"), dict) else {}
                            eb = dict(eb)
                            eb["thinking"] = {"type": "disabled"}
                            forced["extra_body"] = eb
                            forced.pop("reasoning_effort", None)
                            _log_openai_responses_wire_kwargs(
                                forced,
                                variant=f"{cand_label}_thinking_disabled",
                                phase="non_stream_retry_thinking",
                            )
                            resp = self._client.responses.create(**forced)
                            d = _as_dict(resp) or {}
                            text = str(d.get("output_text") or "")
                            tool_calls = _collect_tool_calls_from_response_dict(d)
                            reasoning_text = _reasoning_from_completed_response(d)
                            if on_token and text:
                                on_token(text)
                            if cand_label != input_candidates[0][0]:
                                logger.info(
                                    "openai_responses non-stream: succeeded with input variant %s",
                                    cand_label,
                                )
                            return self._finalize_response(text, tool_calls, reasoning_text)
                        except Exception:
                            pass
                    if _env_truthy("AIA_RESPONSES_LOG_API_ERROR_DETAIL"):
                        eb = getattr(e2, "body", None)
                        if eb is not None:
                            logger.warning(
                                "responses.create non-stream [%s] body: %s", cand_label, eb
                            )
                    if len(input_candidates) > 1 and _is_input_messages_validation_error(e2):
                        nonstream_errors.append(f"{cand_label}:{emsg2}")
                        continue
                    nonstream_errors.append(emsg2)
                    break
            raise RuntimeError(
                "openai_responses_request_failed: "
                + " | ".join([str(exc)] + nonstream_errors[-2:])
            ) from exc


__all__ = ["OpenAIResponsesModel", "parse_openai_responses_stream_events"]

