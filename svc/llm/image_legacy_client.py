"""Legacy image+text payloads for DashScope-style gateways.

Uses ``{"image":...}/{"text":...}`` or typed compatible-mode blocks on ``/chat/completions`` only.
The **image specialist** uses this module from:

- :mod:`~runtime.agents.specialist_agent` (orchestration temp sessions)
- :mod:`~runtime.direct_loop` when ``skill_binding_role=="image"`` (**gateway /chat UI**), so vision
  turns never hit :class:`~svc.llm.transports.openai_responses.OpenAIResponsesModel` unless explicitly disabled via env.

Alignment with Alibaba ``dashscope.MultiModalConversation`` examples (**message shape**):
    ``messages = [{"role": "user", "content": [{"image": "<url or data:...>"}, {"text": "..."}]}]``
matches our non--``typed`` branch (same ``image`` / ``text`` keys as the SDK doc).

Lane separation (**not** OCR):
- Resolved as ``kwargs …`` from the user's **chosen chat model/profile** first, then ``AIA_IMAGE_EXPERT_*`` when a field is empty.
  The **`AIA_OCR_*`** variables remain for **`query_image_attachment`** / OCR downgrade only.
- Bearer HTTP targets ``BASE_URL`` + ``AIA_IMAGE_EXPERT_CHAT_ENDPOINT`` (default ``/chat/completions``), not ``MultiModalConversation`` SDK.

SDK-style extras:
- Optional top-level fields (``stream``, ``n``, ``watermark``, ``negative_prompt``, ``prompt_extend``, ``size``, …):
  use ``DASHSCOPE_IMAGE_*`` env vars or JSON in ``AIA_IMAGE_EXPERT_REQUEST_EXTRA`` (alias: ``AIA_LEGACY_IMAGE_REQUEST_EXTRA``).

Compatibility roots:
- ``compatible-mode/v1`` **默认**使用 OpenAI Chat Completions 视觉块（每条含 ``type``：``image_url`` / ``text``）；百炼兼容网关否则会报 ``missing_required_parameter … content[n].type``。若网关只吃 DashScope 文档形态（无 ``type`` 的 ``{"image"}``/``{"text"}``），设置 ``AIA_IMAGE_EXPERT_COMPAT_USE_DASHSCOPE_NATIVE_BLOCKS=1``。

For OpenAI-style ``image_url`` chat payloads (tool OCR / multimodal downgrade), use :mod:`svc.llm.image_ocr_client`.

Chat UI **图片专家**端到端说明（与其它链路隔离的变更边界）见仓库内 ``docs/IMAGE_SPECIALIST_LANE.md``.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from typing import Any

import httpx

from svc.files.attachment_assets import AttachmentAssetStore
from svc.llm.image_http_common import (
    build_extract_diag_empty,
    compress_data_url_image,
    dashscope_multimodal_http_ok,
    dashscope_native_multimodal_url_from_compatible_base,
    download_http_url_bytes,
    env_image_expert_api_key,
    env_image_expert_base_url,
    env_image_expert_chat_endpoint,
    env_image_expert_model,
    extract_text_and_images,
    format_extract_diag,
    is_data_url,
    join_url,
    post_with_retry,
    redact_response_for_debug,
)
from runtime.prompt_templates import render_prompt

IMAGE_SPECIALIST_DEFAULT_PROMPT_ZH = (
    "请根据用户上传的图片作答：描述可见场景、物体与文字；不确定处请标明。"
)


def _max_legacy_input_images() -> int:
    try:
        v = int(os.getenv("AIA_IMAGE_EXPERT_MAX_INPUT_IMAGES") or "8")
    except Exception:
        v = 8
    return max(1, min(int(v), 12))


def parse_message_attachments_json(raw: Any) -> list[dict[str, Any]]:
    """Decode ``chat_message.attachments`` (JSON string, list, or dict) into attachment dict rows."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s.lower() == "null":
            return []
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
            if isinstance(v, dict):
                return [v]
        except Exception:
            pass
    return []


def collect_legacy_lane_images_from_attachments(
    attachments: list[dict[str, Any]] | None,
    *,
    max_images: int | None = None,
) -> list[str]:
    """Normalize incoming UI/store attachments to URLs/data URLs for :func:`send_legacy_image_messages`."""
    from svc.files.attachment_assets import attachment_id_to_data_url

    cap = max(1, min(int(max_images if max_images is not None else _max_legacy_input_images()), 12))
    out: list[str] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        t = str(att.get("type") or "").strip().lower()
        if t == "image_ref":
            aid = str(att.get("attachment_id") or "").strip()
            if not aid:
                continue
            data_url = attachment_id_to_data_url(aid, mime=str(att.get("mime") or ""))
            if data_url:
                out.append(data_url)
        elif t in ("input_image", "image"):
            raw = str(att.get("image_base64") or att.get("data") or "").strip()
            if raw:
                mime = str(att.get("mime") or "image/jpeg")
                if raw.startswith("data:"):
                    out.append(raw)
                else:
                    out.append(f"data:{mime};base64,{raw}")
        elif t == "image_url":
            u = str(att.get("url") or "").strip()
            if u:
                out.append(u)
        elif t == "relay_pointer":
            mime = str(att.get("mime") or "").strip().lower()
            if mime and not mime.startswith("image/"):
                continue
            uri = str(att.get("pointer_uri") or "").strip()
            aid = str(att.get("attachment_id") or "").strip()
            if not aid and uri:
                m = re.match(r"^relay://attachments/[^/]+/([a-f0-9]{8,128})$", uri, re.I)
                if m:
                    aid = str(m.group(1)).lower()
            if aid:
                data_url = attachment_id_to_data_url(aid, mime=str(att.get("mime") or ""))
                if data_url:
                    out.append(data_url)
        if len(out) >= cap:
            break
    return out


def collect_legacy_lane_images_with_session_fallback(
    *,
    store: Any,
    session_id: str,
    attachments: list[dict[str, Any]] | None,
    max_images: int | None = None,
) -> tuple[list[str], str]:
    """Resolve legacy multimodal image URLs for the current turn, then session history.

    When the current request has no embedded/URL images, scan persisted messages (newest→oldest):
    1) assistant rows with usable image attachments (e.g. last model output);
    2) user rows with images.

    The trailing user bubble for this turn (text-only) is skipped when scanning.

    Returns ``(images, source)`` where ``source`` is ``current``, ``assistant_history``,
    ``user_history``, or empty when nothing was found.

    Disable with ``AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK=0`` (default: on).
    """
    cap = max_images if max_images is not None else _max_legacy_input_images()
    primary = collect_legacy_lane_images_from_attachments(attachments, max_images=cap)
    if primary:
        return primary, "current"
    if str(os.getenv("AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK") or "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return [], ""

    try:
        scan_n = int(os.getenv("AIA_IMAGE_SPECIALIST_FALLBACK_SCAN_MESSAGES") or "400")
    except Exception:
        scan_n = 400
    scan_n = max(1, min(scan_n, 2000))

    try:
        msgs = store.get_messages(str(session_id or "").strip(), limit=scan_n)
    except Exception:
        msgs = []

    if not msgs:
        return [], ""

    hi = len(msgs) - 1
    if hi >= 0:
        last = msgs[hi]
        if str(getattr(last, "role", "") or "").strip().lower() == "user":
            la = parse_message_attachments_json(getattr(last, "attachments", None))
            if not collect_legacy_lane_images_from_attachments(la, max_images=1):
                hi -= 1

    for phase in ("assistant", "user"):
        for i in range(hi, -1, -1):
            m = msgs[i]
            if str(getattr(m, "role", "") or "").strip().lower() != phase:
                continue
            la = parse_message_attachments_json(getattr(m, "attachments", None))
            got = collect_legacy_lane_images_from_attachments(la, max_images=cap)
            if got:
                return got, f"{phase}_history"
    return [], ""


def normalize_legacy_output_image_urls(resp_images: Any, *, max_items: int = 12) -> list[str]:
    """Flatten provider ``images`` / content parts to HTTP/data URLs (strings only)."""
    cap = max(1, min(int(max_items), 24))
    out: list[str] = []
    if resp_images is None:
        return out
    if isinstance(resp_images, str):
        s = resp_images.strip()
        if s:
            out.append(s)
        return out[:cap]
    if not isinstance(resp_images, list):
        return out
    for it in resp_images[:cap]:
        if isinstance(it, str):
            s = it.strip()
            if s:
                out.append(s)
            continue
        if not isinstance(it, dict):
            continue
        u = it.get("image")
        if isinstance(u, str) and u.strip():
            out.append(u.strip())
            continue
        u = it.get("url")
        if isinstance(u, str) and u.strip():
            out.append(u.strip())
            continue
        iu = it.get("image_url")
        if isinstance(iu, str) and iu.strip():
            out.append(iu.strip())
        elif isinstance(iu, dict):
            u2 = iu.get("url")
            if isinstance(u2, str) and u2.strip():
                out.append(u2.strip())
    return out[:cap]


def materialize_legacy_response_output_attachments(
    resp_images: Any,
    *,
    max_images: int = 3,
) -> list[dict[str, Any]]:
    """Persist remote/base64 model outputs as ``image_ref`` / ``image_url`` rows for chat UI."""
    cap = max(1, min(int(max_images), 12))
    produced: list[dict[str, Any]] = []
    urls = normalize_legacy_output_image_urls(resp_images, max_items=cap)
    if not urls:
        return produced
    store = AttachmentAssetStore()
    for idx, item in enumerate(urls[:cap], start=1):
        s = str(item or "").strip()
        if not s:
            continue
        if s.startswith("data:") and ";base64," in s:
            head, b64 = s.split(";base64,", 1)
            mime = head.replace("data:", "", 1) or "image/png"
            try:
                blob = base64.b64decode(b64.encode("ascii"))
            except Exception:
                continue
            meta = store.save_bytes(blob, filename=f"image-output-{idx}.png", mime=mime)
            produced.append(
                {
                    "type": "image_ref",
                    "attachment_id": meta.attachment_id,
                    "name": meta.name,
                    "mime": meta.mime,
                    "bytes": meta.bytes,
                    "width": meta.width,
                    "height": meta.height,
                }
            )
        elif s.startswith("http://") or s.startswith("https://"):
            try:
                blob, ctype = download_http_url_bytes(s)
                if blob:
                    mime = (ctype.split(";", 1)[0].strip() if ctype else "") or "image/png"
                    ext = ".png"
                    if mime == "image/jpeg":
                        ext = ".jpg"
                    elif mime == "image/webp":
                        ext = ".webp"
                    elif mime == "image/gif":
                        ext = ".gif"
                    meta = store.save_bytes(blob, filename=f"image-output-{idx}{ext}", mime=mime)
                    produced.append(
                        {
                            "type": "image_ref",
                            "attachment_id": meta.attachment_id,
                            "name": meta.name,
                            "mime": meta.mime,
                            "bytes": meta.bytes,
                            "width": meta.width,
                            "height": meta.height,
                        }
                    )
                    continue
            except Exception:
                pass
            produced.append({"type": "image_url", "url": s, "name": f"image-output-{idx}.png"})
    return produced


def legacy_image_turn_bundle(resp: dict[str, Any]) -> tuple[bool, str, list[dict[str, Any]]]:
    """Interpret ``send_legacy_image_messages`` result for persistence (text-only vision answers allowed)."""
    ok = bool(resp.get("ok"))
    text = str(resp.get("text") or "").strip()
    if not ok:
        err = str(resp.get("error") or "").strip()
        return False, f"Image generation failed: {err or 'unknown error'}", []
    raw_urls = normalize_legacy_output_image_urls(resp.get("images"), max_items=6)
    imgs = materialize_legacy_response_output_attachments(raw_urls, max_images=3)
    if not imgs and raw_urls:
        imgs = [
            {"type": "image_url", "url": u, "name": f"image-output-{i}.png"}
            for i, u in enumerate(raw_urls[:3], start=1)
            if u.startswith(("http://", "https://", "data:"))
        ]
    if imgs:
        return True, text, imgs
    if text:
        return True, text, []
    diag = resp.get("extract_diag")
    hint = ""
    if isinstance(diag, dict) and diag:
        hint = format_extract_diag(diag, max_chars=1400)
    red = resp.get("provider_response_redacted")
    if isinstance(red, str) and red.strip():
        hint = f"{hint}\nprovider_json={red.strip()}" if hint else f"provider_json={red.strip()}"
    base = "Image specialist failed: empty response from provider."
    out_msg = f"{base} {hint}".strip()
    if len(out_msg) > 12_000:
        out_msg = out_msg[:11_980] + "\n…<truncated>"
    return False, out_msg, []


def legacy_image_assistant_body_with_placeholder(
    *,
    lang: str | None,
    body_text: str,
    produced: list[dict[str, Any]] | None,
) -> str:
    """If the model returned images but no visible text, use the standard chat placeholder (ZH/EN).

    Shared by ``direct_loop`` (gateway /chat) and ``specialist_agent`` (temp sessions).
    """
    if str(body_text or "").strip():
        return str(body_text or "")
    if produced:
        return (
            "Generated image (see attachment below)."
            if str(lang or "").startswith("en")
            else "已生成图片（见下方附件）。"
        )
    return str(body_text or "")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _redact_payload_for_stderr(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _redact_payload_for_stderr(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_payload_for_stderr(x) for x in obj]
    if isinstance(obj, str):
        s = obj
        if ";base64," in s and s.strip().startswith("data:") and len(s) > 120:
            h, _, _ = s.partition(";base64,")
            return f"{h};base64,<redacted ~{len(s) - len(h) - 8} chars>"
        return s
    return obj


def _stderr_debug_image_legacy(url: str, payload: dict[str, Any]) -> None:
    if not _truthy_env("AIA_IMAGE_EXPERT_DEBUG_PRINT_PAYLOAD"):
        return
    try:
        txt = json.dumps(_redact_payload_for_stderr(dict(payload)), ensure_ascii=False, indent=2, default=str)
        sys.stderr.write(f"\n[oclaw image_legacy] POST {url}\n{txt}\n\n")
        sys.stderr.flush()
    except Exception:
        pass


def _extra_request_fields_from_env() -> dict[str, Any]:
    """Merge JSON from ``AIA_IMAGE_EXPERT_REQUEST_EXTRA`` (or legacy alias ``AIA_LEGACY_IMAGE_REQUEST_EXTRA``)."""
    raw = (os.getenv("AIA_IMAGE_EXPERT_REQUEST_EXTRA") or os.getenv("AIA_LEGACY_IMAGE_REQUEST_EXTRA") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _dashscope_image_env_kw() -> dict[str, Any]:
    """Map `_local/system.env.example` ``DASHSCOPE_IMAGE_*`` vars to multimodal/top-level kwargs (parity with SDK samples)."""
    out: dict[str, Any] = {}
    raw_n = (os.getenv("DASHSCOPE_IMAGE_N") or "").strip()
    if raw_n.isdigit():
        out["n"] = max(1, min(int(raw_n), 6))

    wm = (os.getenv("DASHSCOPE_IMAGE_WATERMARK") or "").strip().lower()
    if wm in ("1", "true", "yes", "on"):
        out["watermark"] = True
    elif wm in ("0", "false", "no", "off"):
        out["watermark"] = False

    raw_stream = (os.getenv("DASHSCOPE_IMAGE_STREAM") or "").strip().lower()
    if raw_stream in ("1", "true", "yes", "on"):
        out["stream"] = True
    elif raw_stream in ("0", "false", "no", "off"):
        out["stream"] = False

    neg = os.getenv("DASHSCOPE_IMAGE_NEGATIVE_PROMPT")
    if neg is not None:
        ns = str(neg)
        if ns.strip():
            out["negative_prompt"] = ns

    pe = (os.getenv("DASHSCOPE_IMAGE_PROMPT_EXTEND") or "").strip().lower()
    if pe in ("1", "true", "yes", "on"):
        out["prompt_extend"] = True
    elif pe in ("0", "false", "no", "off"):
        out["prompt_extend"] = False

    size = (os.getenv("DASHSCOPE_IMAGE_SIZE") or "").strip()
    if size:
        out["size"] = size

    return out


def _openai_compatible_vision_content(images: list[str], prompt_text: str) -> list[dict[str, Any]]:
    """OpenAI Chat Completions vision shape (``type`` + ``image_url`` / ``text``).

    Required for typical ``compatible-mode/v1`` ``/chat/completions`` (each part must have ``type``).
    Image URLs may be ``https://…`` or ``data:image/…;base64,…``.
    """
    blocks: list[dict[str, Any]] = []
    for img in images:
        blocks.append({"type": "image_url", "image_url": {"url": img}})
    blocks.append({"type": "text", "text": str(prompt_text or "").strip()})
    return blocks


def _compat_use_dashscope_native_blocks() -> bool:
    """When ``1``, ``compatible-mode`` URLs use DashScope doc blocks without ``type`` (see :func:`_http_content_blocks`)."""
    return str(os.getenv("AIA_IMAGE_EXPERT_COMPAT_USE_DASHSCOPE_NATIVE_BLOCKS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _model_triggers_dashscope_native_fallback(model_name: str) -> bool:
    """``qwen-image`` on OpenAI-compat ``/chat/completions`` often returns ``message.content=null``."""
    if str(os.getenv("AIA_IMAGE_EXPERT_DISABLE_DASHSCOPE_NATIVE_FALLBACK") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    if str(os.getenv("AIA_IMAGE_EXPERT_FORCE_DASHSCOPE_NATIVE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    m = (model_name or "").strip().lower()
    needle = (os.getenv("AIA_IMAGE_EXPERT_NATIVE_FALLBACK_MODEL_SUBSTR") or "qwen-image").strip().lower()
    return bool(needle) and needle in m


def _http_content_blocks(images: list[str], prompt: str, *, typed: bool) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    if not typed:
        blocks: list[dict[str, Any]] = [{"image": img} for img in images]
        blocks.append({"text": prompt_text})
        return blocks
    blocks_typed: list[dict[str, Any]] = [{"type": "image", "image": img} for img in images]
    blocks_typed.append({"type": "text", "text": prompt_text})
    return blocks_typed


def send_legacy_image_messages(
    *,
    images: list[str],
    prompt: str,
    model: str | None = None,
    timeout_sec: int = 60,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Legacy multimodal HTTP (non--OpenAI-``image_url`` schema); image specialist uses this entry point."""
    resolved_base_url = (base_url or env_image_expert_base_url()).strip()
    resolved_api_key = (api_key or env_image_expert_api_key()).strip()
    model_name = ((model or "").strip() or env_image_expert_model())
    endpoint = env_image_expert_chat_endpoint()
    url = join_url(resolved_base_url, endpoint)
    if not resolved_api_key or not resolved_base_url:
        return {
            "ok": False,
            "error": "missing AIA_IMAGE_EXPERT_API_KEY or AIA_IMAGE_EXPERT_BASE_URL (or pass api_key and base_url)",
        }
    if not model_name:
        return {
            "ok": False,
            "error": "missing model (chosen profile/model=… or set AIA_IMAGE_EXPERT_MODEL)",
        }
    if not images:
        return {"ok": False, "error": "at least one image input is required"}

    raw_selected = [str(x).strip() for x in images if str(x).strip()][: _max_legacy_input_images()]
    selected: list[str] = []
    input_kind: list[str] = []
    for img in raw_selected:
        if is_data_url(img):
            selected.append(compress_data_url_image(img))
            input_kind.append("data_url")
            continue
        if img.startswith("http://") or img.startswith("https://"):
            selected.append(img)
            input_kind.append("url")
            continue
    if not selected:
        return {"ok": False, "error": "no usable image input (expected URL or data URL)"}

    # compatible-mode /chat/completions is OpenAI-shaped: every content part needs ``type`` (else 400 missing content[n].type).
    # Native DashScope HTTP (non-compatible base) uses ``{"image"}`` / ``{"text"}`` without ``type``.
    use_compatible_base = "compatible-mode" in resolved_base_url.lower()
    prompt_plain = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    if use_compatible_base and not _compat_use_dashscope_native_blocks():
        content_multi = _openai_compatible_vision_content(selected, prompt_plain)
    else:
        content_multi = _http_content_blocks(selected, prompt, typed=False)

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    extra_ds = _dashscope_image_env_kw()
    extra_json = _extra_request_fields_from_env()
    extra = {**extra_ds, **extra_json}
    core_multi = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_multi}],
    }
    payload_multi = {**extra, **core_multi}

    _stderr_debug_image_legacy(url, payload_multi)

    with httpx.Client(timeout=float(timeout_sec)) as client:
        try:
            r = post_with_retry(client, url=url, headers=headers, payload=payload_multi)
        except Exception as e:
            return {"ok": False, "error": f"http request failed: {type(e).__name__}: {e}", "backend_shape": "multi"}

        if r.status_code >= 400:
            return {"ok": False, "error": f"http {r.status_code}: {r.text[:800]}", "backend_shape": "multi"}

        try:
            obj = r.json()
        except Exception:
            return {"ok": False, "error": f"non-json response: {r.text[:500]}", "backend_shape": "multi"}
        if not isinstance(obj, dict):
            return {
                "ok": False,
                "error": f"expected JSON object from provider, got {type(obj).__name__}",
                "backend_shape": "multi",
                "input_kind": input_kind if input_kind else ["data_url"],
            }
        body = obj
        ds_ok, ds_err = dashscope_multimodal_http_ok(body)
        if not ds_ok:
            return {
                "ok": False,
                "error": ds_err or "provider rejected request (DashScope code/message)",
                "backend_shape": "multi",
                "input_kind": input_kind if input_kind else ["data_url"],
            }
        text, out_images = extract_text_and_images(body)
        compat_extract_diag: dict[str, Any] | None = None
        native_fallback_meta: dict[str, Any] = {}

        if (
            not str(text or "").strip()
            and not out_images
            and use_compatible_base
            and _model_triggers_dashscope_native_fallback(model_name)
        ):
            compat_extract_diag = build_extract_diag_empty(body)
            native_url = dashscope_native_multimodal_url_from_compatible_base(resolved_base_url)
            if not native_url:
                native_fallback_meta = {
                    "attempted": False,
                    "hint": "set AIA_IMAGE_EXPERT_DASHSCOPE_NATIVE_URL or use a compatible-mode base_url",
                }
            else:
                content_native = _http_content_blocks(selected, prompt, typed=False)
                param_merge = {**_dashscope_image_env_kw(), **_extra_request_fields_from_env()}
                param_merge.pop("stream", None)
                payload_native = {
                    "model": model_name,
                    "input": {"messages": [{"role": "user", "content": content_native}]},
                    "parameters": {"result_format": "message", **param_merge},
                }
                _stderr_debug_image_legacy(native_url, payload_native)
                try:
                    r2 = post_with_retry(client, url=native_url, headers=headers, payload=payload_native)
                except Exception as e:
                    native_fallback_meta = {
                        "attempted": True,
                        "url": native_url,
                        "error": f"{type(e).__name__}: {e}",
                    }
                else:
                    if r2.status_code >= 400:
                        native_fallback_meta = {
                            "attempted": True,
                            "url": native_url,
                            "http_status": int(r2.status_code),
                            "body_head": r2.text[:600],
                        }
                    else:
                        try:
                            b2 = r2.json()
                        except Exception as e:
                            native_fallback_meta = {
                                "attempted": True,
                                "url": native_url,
                                "error": f"json: {type(e).__name__}: {e}",
                            }
                        else:
                            if isinstance(b2, dict):
                                ok2, err2 = dashscope_multimodal_http_ok(b2)
                                if not ok2:
                                    native_fallback_meta = {
                                        "attempted": True,
                                        "url": native_url,
                                        "dashscope_error": err2 or "business code",
                                    }
                                else:
                                    t2, im2 = extract_text_and_images(b2)
                                    if str(t2 or "").strip() or im2:
                                        text, out_images = t2, im2
                                        body = b2
                                        native_fallback_meta = {
                                            "attempted": True,
                                            "url": native_url,
                                            "succeeded": True,
                                        }
                                    else:
                                        native_fallback_meta = {
                                            "attempted": True,
                                            "url": native_url,
                                            "succeeded": False,
                                            "native_diag": build_extract_diag_empty(b2),
                                        }
                            else:
                                native_fallback_meta = {
                                    "attempted": True,
                                    "url": native_url,
                                    "error": "native response not a JSON object",
                                }

        extract_diag: dict[str, Any] | None = None
        provider_response_redacted: str | None = None
        if not str(text or "").strip() and not out_images:
            extract_diag = build_extract_diag_empty(body)
            if compat_extract_diag is not None:
                extract_diag["openai_compat_empty"] = compat_extract_diag
            if native_fallback_meta:
                extract_diag["dashscope_native_fallback"] = native_fallback_meta
            provider_response_redacted = redact_response_for_debug(body, max_chars=3200)
            if _truthy_env("AIA_IMAGE_EXPERT_DEBUG_PRINT_PAYLOAD"):
                try:
                    sys.stderr.write(
                        "\n[oclaw image_legacy] extract_empty extract_diag="
                        + format_extract_diag(extract_diag, max_chars=4000)
                        + "\n"
                        + (provider_response_redacted or "")
                        + "\n\n"
                    )
                    sys.stderr.flush()
                except Exception:
                    pass
        out_images = normalize_legacy_output_image_urls(out_images, max_items=12)
        return {
            "ok": True,
            "text": text,
            "images": out_images,
            "backend_shape": "multi",
            "input_kind": input_kind if input_kind else ["data_url"],
            "extract_diag": extract_diag,
            "provider_response_redacted": provider_response_redacted,
        }


__all__ = [
    "IMAGE_SPECIALIST_DEFAULT_PROMPT_ZH",
    "collect_legacy_lane_images_from_attachments",
    "collect_legacy_lane_images_with_session_fallback",
    "parse_message_attachments_json",
    "legacy_image_assistant_body_with_placeholder",
    "legacy_image_turn_bundle",
    "materialize_legacy_response_output_attachments",
    "normalize_legacy_output_image_urls",
    "send_legacy_image_messages",
]
