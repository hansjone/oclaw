"""Shared HTTP helpers for OCR and legacy image lanes (internal)."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from typing import Any

import httpx
from PIL import Image


def join_url(base: str, path: str) -> str:
    b = (base or "").rstrip("/")
    p = (path or "").lstrip("/")
    return f"{b}/{p}"


def dashscope_native_multimodal_url_from_compatible_base(base_url: str) -> str | None:
    """
    ``qwen-image`` and similar models often return an **empty** OpenAI ``chat/completions`` message on
    ``/compatible-mode/v1``. Native HTTP uses ``/api/v1/services/aigc/multimodal-generation/generation``
    and returns ``output.choices[].message.content[].image`` URLs.

    Override: ``AIA_IMAGE_EXPERT_DASHSCOPE_NATIVE_URL`` (full URL).
    Path suffix: ``AIA_IMAGE_EXPERT_DASHSCOPE_NATIVE_PATH`` (default multimodal-generation path).
    """
    explicit = (os.getenv("AIA_IMAGE_EXPERT_DASHSCOPE_NATIVE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    b = (base_url or "").strip().rstrip("/")
    if not b or "compatible-mode" not in b.lower():
        return None
    root = re.sub(r"/compatible-mode/v\d+(?:/.*)?$", "", b, flags=re.IGNORECASE).rstrip("/")
    if not root or root == b:
        root = re.sub(r"/compatible-mode/?$", "", b, flags=re.IGNORECASE).rstrip("/")
    if not root:
        return None
    path = (os.getenv("AIA_IMAGE_EXPERT_DASHSCOPE_NATIVE_PATH") or "").strip().lstrip("/")
    if not path:
        path = "api/v1/services/aigc/multimodal-generation/generation"
    return f"{root}/{path}"


def env_ocr_lane_api_key() -> str:
    return (os.getenv("AIA_OCR_API_KEY") or "").strip()


def env_ocr_lane_base_url() -> str:
    return (os.getenv("AIA_OCR_BASE_URL") or "").strip()


def env_ocr_lane_model() -> str:
    return (os.getenv("AIA_OCR_MODEL") or "").strip()


def env_ocr_lane_chat_endpoint() -> str:
    raw = (os.getenv("AIA_OCR_CHAT_ENDPOINT") or "").strip()
    return raw or "/chat/completions"


def env_image_expert_api_key() -> str:
    """Bearer key for **image specialist** multimodal/gen HTTP only (never shared with OCR ``AIA_OCR_*``)."""

    return (os.getenv("AIA_IMAGE_EXPERT_API_KEY") or "").strip()


def env_image_expert_base_url() -> str:
    return (os.getenv("AIA_IMAGE_EXPERT_BASE_URL") or "").strip()


def env_image_expert_model() -> str:
    return (os.getenv("AIA_IMAGE_EXPERT_MODEL") or "").strip()


def env_image_expert_chat_endpoint() -> str:
    raw = (os.getenv("AIA_IMAGE_EXPERT_CHAT_ENDPOINT") or "").strip()
    return raw or "/chat/completions"


def is_data_url(s: str) -> bool:
    return s.startswith("data:") and ";base64," in s


def compress_data_url_image(
    data_url: str,
    *,
    max_side: int = 1600,
    max_bytes: int = 2 * 1024 * 1024,
    jpeg_quality: int = 82,
) -> str:
    if not is_data_url(data_url):
        return data_url
    try:
        header, b64 = data_url.split(";base64,", 1)
        mime = header.replace("data:", "", 1).strip() or "image/jpeg"
        raw = base64.b64decode(b64.encode("ascii"))
        if len(raw) <= max_bytes:
            return data_url

        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            w, h = im.size
            longest = max(w, h)
            if longest > max_side:
                scale = max_side / float(longest)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)

            out = io.BytesIO()
            im.save(out, format="JPEG", quality=max(30, min(95, int(jpeg_quality))), optimize=True)
            blob = out.getvalue()
            if not blob:
                return data_url
            b64_new = base64.b64encode(blob).decode("ascii")
            return f"data:{'image/jpeg' if mime.startswith('image/') else mime};base64,{b64_new}"
    except Exception:
        return data_url


def post_with_retry(
    client: httpx.Client,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    retries: int = 3,
    backoff_sec: float = 0.8,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return client.post(url, headers=headers, json=payload)
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt >= retries:
                break
            time.sleep(backoff_sec * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc


def env_image_expert_download_timeout_sec() -> float:
    """Read timeout for DashScope/OSS signed result URLs (official samples use ~300s)."""
    raw = (os.getenv("AIA_IMAGE_EXPERT_DOWNLOAD_TIMEOUT_SEC") or "").strip()
    if not raw:
        return 300.0
    try:
        v = float(raw)
    except ValueError:
        return 300.0
    return max(15.0, min(v, 900.0))


def download_http_url_bytes(
    url: str,
    *,
    timeout_sec: float | None = None,
    user_agent: str | None = None,
) -> tuple[bytes, str]:
    """Streamed GET with ``raise_for_status`` — matches DashScope OSS download guidance (long reads)."""
    t = float(timeout_sec) if timeout_sec is not None else env_image_expert_download_timeout_sec()
    ua = (user_agent or "").strip() or (
        "Mozilla/5.0 (compatible; oclaw-image-expert/1.0; +https://github.com/)"
    )
    req_headers = {"User-Agent": ua, "Accept": "*/*"}
    connect_cap = min(45.0, max(10.0, t / 10.0))
    timeout = httpx.Timeout(t, connect=connect_cap)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", url, headers=req_headers) as r:
            r.raise_for_status()
            ctype = str(r.headers.get("content-type") or "").split(";", 1)[0].strip()
            parts: list[bytes] = []
            for chunk in r.iter_bytes(chunk_size=65_536):
                parts.append(chunk)
    return b"".join(parts), ctype


def dashscope_multimodal_http_ok(body: dict[str, Any]) -> tuple[bool, str]:
    """DashScope HTTP often uses HTTP 200 with a business-level ``code`` for failures."""
    sc = body.get("status_code")
    if isinstance(sc, str) and sc.strip().isdigit():
        sc = int(sc.strip())
    if isinstance(sc, int) and sc >= 400:
        return False, str(body.get("message") or body.get("msg") or f"status_code={sc}")
    code = body.get("code")
    if code is None:
        return True, ""
    if isinstance(code, int):
        if code == 200:
            return True, ""
        msg = str(body.get("message") or body.get("msg") or "").strip()
        return False, msg or str(code)
    cs = str(code).strip()
    if cs == "":
        return True, ""
    if cs.lower() in ("success", "ok", "200"):
        return True, ""
    msg = str(body.get("message") or body.get("msg") or "").strip()
    return False, msg or cs


def _extract_response_roots(resp_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect dict slices that may carry ``choices`` / ``messages`` (DashScope nests under ``output``)."""
    roots: list[dict[str, Any]] = []
    seen: set[int] = set()

    def push(d: dict[str, Any]) -> None:
        i = id(d)
        if i in seen:
            return
        seen.add(i)
        roots.append(d)

    push(resp_json)
    nested = resp_json.get("output")
    if isinstance(nested, dict):
        push(nested)
        deeper = nested.get("output")
        if isinstance(deeper, dict):
            push(deeper)
    result = resp_json.get("result")
    if isinstance(result, dict):
        push(result)
    data_obj = resp_json.get("data")
    if isinstance(data_obj, dict):
        push(data_obj)
    return roots


def _append_image_from_any(images: list[str], raw: Any) -> None:
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        if s.startswith(("http://", "https://", "data:")):
            images.append(s)
        return
    if isinstance(raw, dict):
        u = raw.get("url")
        if isinstance(u, str) and u.strip() and u.strip().startswith(("http://", "https://")):
            images.append(u.strip())


def _parse_content_part(it: Any, *, text_parts: list[str], images: list[str]) -> None:
    """Parse one multimodal element (DashScope shorthand, OpenAI-style typed blocks, etc.)."""
    if isinstance(it, str) and it.strip():
        text_parts.append(it.strip())
        return
    if not isinstance(it, dict):
        return
    typ = str(it.get("type") or "").strip().lower()
    if typ == "text":
        tx = it.get("text")
        if isinstance(tx, str) and tx.strip():
            text_parts.append(tx.strip())
        return
    if typ == "input_text":
        tx = it.get("text")
        if isinstance(tx, str) and tx.strip():
            text_parts.append(tx.strip())
        return
    if typ == "image_url":
        iu = it.get("image_url")
        if isinstance(iu, dict):
            _append_image_from_any(images, iu)
        elif isinstance(iu, str):
            _append_image_from_any(images, iu)
        return
    if typ == "input_image":
        iu = it.get("image_url")
        if isinstance(iu, dict):
            _append_image_from_any(images, iu)
        elif isinstance(iu, str):
            _append_image_from_any(images, iu)
        return
    if typ == "image" and it.get("image") is not None:
        _append_image_from_any(images, it.get("image"))
        return
    # Untyped / DashScope shorthand blocks
    tx = it.get("text")
    if isinstance(tx, str) and tx.strip():
        text_parts.append(tx.strip())
    if it.get("image") is not None:
        _append_image_from_any(images, it.get("image"))
    ius = it.get("image_url")
    if isinstance(ius, str):
        _append_image_from_any(images, ius)
    elif isinstance(ius, dict):
        _append_image_from_any(images, ius)
    uu = it.get("url")
    if isinstance(uu, str) and uu.strip().startswith(("http://", "https://")):
        images.append(uu.strip())
    if isinstance(it.get("b64_json"), str) and str(it.get("b64_json")).strip():
        images.append(f"data:image/png;base64,{it['b64_json']}")


def _try_parse_content_json_string(raw: str, *, text_parts: list[str], images: list[str]) -> bool:
    """Some proxies stringify multimodal ``content`` as JSON."""
    s = raw.strip()
    if not s or s[0] not in "[{":
        return False
    try:
        parsed = json.loads(s)
    except Exception:
        return False
    if isinstance(parsed, list):
        for it in parsed:
            _parse_content_part(it, text_parts=text_parts, images=images)
        return True
    if isinstance(parsed, dict):
        _parse_content_part(parsed, text_parts=text_parts, images=images)
        return True
    return False


def _harvest_http_urls_from_value(val: Any, images: list[str], *, depth: int, max_depth: int = 6) -> None:
    """Last resort: collect image URLs nested under ``message`` (unknown multimodal block shapes)."""
    if depth > max_depth or val is None:
        return
    if isinstance(val, str):
        s = val.strip()
        if s.startswith(("http://", "https://")) and s not in images:
            images.append(s)
        return
    if isinstance(val, dict):
        for _k, v in val.items():
            _harvest_http_urls_from_value(v, images, depth=depth + 1, max_depth=max_depth)
        return
    if isinstance(val, list):
        for it in val:
            _harvest_http_urls_from_value(it, images, depth=depth + 1, max_depth=max_depth)


def _parse_choice_message_content(msg: dict[str, Any], *, text_parts: list[str], images: list[str]) -> None:
    c = msg.get("content")
    if c is None:
        _harvest_http_urls_from_value(msg, images, depth=0)
        return
    if isinstance(c, str):
        if c.strip() and _try_parse_content_json_string(c, text_parts=text_parts, images=images):
            _harvest_http_urls_from_value(msg, images, depth=0)
            return
        if c.strip():
            text_parts.append(c.strip())
        _harvest_http_urls_from_value(msg, images, depth=0)
        return
    if isinstance(c, dict):
        _parse_content_part(c, text_parts=text_parts, images=images)
        _harvest_http_urls_from_value(msg, images, depth=0)
        return
    if isinstance(c, list):
        for it in c:
            _parse_content_part(it, text_parts=text_parts, images=images)
        _harvest_http_urls_from_value(msg, images, depth=0)
        return


def _parse_messages_array_for_assistant(
    messages: list[Any], *, text_parts: list[str], images: list[str]
) -> None:
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "").strip().lower() != "assistant":
            continue
        _parse_choice_message_content(m, text_parts=text_parts, images=images)
        break


def extract_text_and_images(resp_json: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    images: list[str] = []
    roots = _extract_response_roots(resp_json)

    for root in roots:
        ot = root.get("text")
        if isinstance(ot, str) and ot.strip():
            text_parts.append(ot.strip())

    choices: list[Any] | None = None
    for root in roots:
        ch = root.get("choices")
        if isinstance(ch, list) and ch:
            choices = ch
            break

    if isinstance(choices, list) and choices:
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            legacy_txt = choice.get("text")
            if isinstance(legacy_txt, str) and legacy_txt.strip():
                text_parts.append(legacy_txt.strip())
            msg = choice.get("message")
            if isinstance(msg, dict):
                _parse_choice_message_content(msg, text_parts=text_parts, images=images)
            elif not isinstance(msg, dict):
                _harvest_http_urls_from_value(choice, images, depth=0)

    if not text_parts and not images:
        for root in roots:
            msgs = root.get("messages")
            if isinstance(msgs, list) and msgs:
                _parse_messages_array_for_assistant(msgs, text_parts=text_parts, images=images)
                if text_parts or images:
                    break

    if not images:
        for root in roots:
            data = root.get("data")
            if not isinstance(data, list):
                continue
            for it in data:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("url"), str) and str(it.get("url")).strip():
                    images.append(str(it.get("url")).strip())
                if isinstance(it.get("b64_json"), str) and str(it.get("b64_json")).strip():
                    images.append(f"data:image/png;base64,{it['b64_json']}")

    if not images:
        for root in roots:
            for key in ("results", "artifacts", "task_outputs"):
                arr = root.get(key)
                if not isinstance(arr, list):
                    continue
                for it in arr:
                    if not isinstance(it, dict):
                        continue
                    for ik in ("image", "url", "output_image_url", "image_url"):
                        v = it.get(ik)
                        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
                            images.append(v.strip())
                        elif isinstance(v, dict) and isinstance(v.get("url"), str):
                            u = str(v.get("url")).strip()
                            if u.startswith(("http://", "https://")):
                                images.append(u)

    # De-dupe URLs while preserving order
    seen_u: set[str] = set()
    uniq_images: list[str] = []
    for u in images:
        if u not in seen_u:
            seen_u.add(u)
            uniq_images.append(u)
    images = uniq_images

    return "\n".join([x for x in text_parts if x]).strip(), images


def _diag_fill_choices(out: dict[str, Any], ch: Any, *, prefix: str) -> None:
    out[f"{prefix}choices_typename"] = type(ch).__name__
    out[f"{prefix}choices_len"] = len(ch) if isinstance(ch, list) else None
    if not isinstance(ch, list) or not ch or not isinstance(ch[0], dict):
        return
    c0 = ch[0]
    out[f"{prefix}choice0_keys"] = sorted(c0.keys())[:24]
    msg = c0.get("message")
    if isinstance(msg, dict):
        out[f"{prefix}msg_keys"] = sorted(msg.keys())[:24]
        c = msg.get("content")
        out[f"{prefix}content_typename"] = type(c).__name__
        if isinstance(c, list):
            out[f"{prefix}content_len"] = len(c)
            if c:
                out[f"{prefix}content0_typename"] = type(c[0]).__name__
                if isinstance(c[0], dict):
                    out[f"{prefix}content0_keys"] = sorted(c[0].keys())[:24]
        elif isinstance(c, dict):
            out[f"{prefix}content_keys"] = sorted(c.keys())[:24]
        elif c is None:
            out[f"{prefix}content_is_null"] = True


def build_extract_diag_empty(obj: dict[str, Any]) -> dict[str, Any]:
    """Compact shape hints when extraction yielded nothing (stderr / chat debug)."""
    out: dict[str, Any] = {"top_level_keys": sorted(obj.keys())[:40]}
    ch_top = obj.get("choices")
    if ch_top is not None:
        _diag_fill_choices(out, ch_top, prefix="")
    outp = obj.get("output")
    if isinstance(outp, dict):
        out["output_keys"] = sorted(outp.keys())[:40]
        ch = outp.get("choices")
        _diag_fill_choices(out, ch, prefix="output_")
    return out


def redact_response_for_debug(obj: Any, *, max_chars: int = 2800) -> str:
    """JSON preview for error surfaces (truncate; redact long base64 / data URLs)."""

    def _walk(x: Any) -> Any:
        if isinstance(x, dict):
            return {str(k): _walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [_walk(v) for v in x[:80]]
        if isinstance(x, str):
            s = x
            if ";base64," in s and s.strip().startswith("data:") and len(s) > 120:
                h, _, _ = s.partition(";base64,")
                return f"{h};base64,<redacted {len(s)} chars>"
            if len(s) > 500:
                return s[:400] + f"...<truncated {len(s) - 400}>"
            return s
        return x

    try:
        txt = json.dumps(_walk(obj), ensure_ascii=False, default=str)
    except Exception:
        txt = str(obj)
    if len(txt) > max_chars:
        return txt[: max_chars - 24] + "\n…<truncated>"
    return txt


def format_extract_diag(diag: dict[str, Any], *, max_chars: int = 900) -> str:
    try:
        s = json.dumps(diag, ensure_ascii=False, default=str)
    except Exception:
        s = str(diag)
    if len(s) > max_chars:
        return s[: max_chars - 20] + "…<truncated>"
    return s


__all__ = [
    "build_extract_diag_empty",
    "compress_data_url_image",
    "dashscope_multimodal_http_ok",
    "dashscope_native_multimodal_url_from_compatible_base",
    "download_http_url_bytes",
    "env_image_expert_download_timeout_sec",
    "redact_response_for_debug",
    "env_image_expert_api_key",
    "env_image_expert_base_url",
    "env_image_expert_chat_endpoint",
    "env_image_expert_model",
    "env_ocr_lane_api_key",
    "env_ocr_lane_base_url",
    "env_ocr_lane_chat_endpoint",
    "env_ocr_lane_model",
    "extract_text_and_images",
    "format_extract_diag",
    "is_data_url",
    "join_url",
    "post_with_retry",
]
