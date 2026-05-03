from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

import httpx
from PIL import Image
from oclaw.runtime.prompt_templates import render_prompt


def _summarize_data_url(url: str) -> dict[str, Any]:
    """
    Summarize data URLs without logging raw base64 payload.
    """
    s = str(url or "")
    if not s.startswith("data:"):
        return {"kind": "url", "prefix": s[:30]}
    mime = "image/jpeg"
    try:
        # data:{mime};base64,{b64}
        head = s.split(";", 1)[0]  # data:image/xxx
        if head.startswith("data:"):
            mime = head[len("data:") :] or mime
    except Exception:
        pass
    b64_part = s.split(",", 1)[1] if "," in s else ""
    has_b64 = ";base64," in s
    return {"kind": "data_url", "mime": mime, "has_base64": has_b64, "b64_len": len(b64_part)}


def _summarize_dashscope_messages(messages: list[dict[str, Any]], *, max_items: int = 3) -> dict[str, Any]:
    """
    Debug-only summary of messages[0].content structure.
    """
    if not messages or not isinstance(messages, list):
        return {"content_items": []}
    first = messages[0] if messages else {}
    if not isinstance(first, dict):
        return {"content_items": []}
    content = first.get("content")
    if not isinstance(content, list):
        return {"content_items": []}
    out: list[dict[str, Any]] = []
    for it in content[:max_items]:
        if not isinstance(it, dict):
            out.append({"item_type": "non_dict"})
            continue
        item: dict[str, Any] = {"keys": sorted([str(k) for k in it.keys()])}
        if "type" in it:
            item["type"] = it.get("type")
        if "image" in it:
            item["image"] = _summarize_data_url(str(it.get("image") or ""))
        if "image_url" in it:
            iu = it.get("image_url")
            if isinstance(iu, dict) and "url" in iu:
                item["image_url"] = _summarize_data_url(str(iu.get("url") or ""))
            else:
                item["image_url"] = {"kind": "image_url_non_dict"}
        if "text" in it:
            item["text_len"] = len(str(it.get("text") or ""))
        out.append(item)
    return {"content_items": out}


def _join_url(base: str, path: str) -> str:
    b = (base or "").rstrip("/")
    p = (path or "").lstrip("/")
    return f"{b}/{p}"


def _is_data_url(s: str) -> bool:
    return s.startswith("data:") and ";base64," in s


def _compress_data_url_image(
    data_url: str,
    *,
    max_side: int = 1600,
    max_bytes: int = 2 * 1024 * 1024,
    jpeg_quality: int = 82,
) -> str:
    """Best-effort compress image data URLs to reduce transport failures."""
    if not _is_data_url(data_url):
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
            # Use JPEG for broad compatibility and smaller payload.
            im.save(out, format="JPEG", quality=max(30, min(95, int(jpeg_quality))), optimize=True)
            blob = out.getvalue()
            if not blob:
                return data_url
            b64_new = base64.b64encode(blob).decode("ascii")
            return f"data:{'image/jpeg' if mime.startswith('image/') else mime};base64,{b64_new}"
    except Exception:
        return data_url


def _post_with_retry(
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


def _extract_text_and_images(resp_json: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    images: list[str] = []
    choices = resp_json.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str):
                text_parts.append(c)
            elif isinstance(c, list):
                for it in c:
                    if not isinstance(it, dict):
                        continue
                    if isinstance(it.get("text"), str):
                        text_parts.append(str(it.get("text")))
                    elif isinstance(it.get("image"), str):
                        images.append(str(it.get("image")))
                    elif isinstance(it.get("image_url"), str):
                        images.append(str(it.get("image_url")))
                    elif isinstance(it.get("image_url"), dict) and isinstance(it["image_url"].get("url"), str):
                        images.append(str(it["image_url"]["url"]))
                    elif isinstance(it.get("b64_json"), str):
                        images.append(f"data:image/png;base64,{it['b64_json']}")

    # fallback for image APIs that return data[0].b64_json/url
    if not images:
        data = resp_json.get("data")
        if isinstance(data, list):
            for it in data:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("url"), str):
                    images.append(str(it.get("url")))
                if isinstance(it.get("b64_json"), str):
                    images.append(f"data:image/png;base64,{it['b64_json']}")
    return "\n".join([x for x in text_parts if x]).strip(), images


def _extract_from_dashscope_response(resp: Any) -> tuple[str, list[str], str]:
    """Parse dashscope SDK response object (or dict-like) into text/images."""
    text_parts: list[str] = []
    images: list[str] = []

    def _as_dict(x: Any) -> dict[str, Any]:
        if isinstance(x, dict):
            return x
        if hasattr(x, "__dict__"):
            try:
                return dict(vars(x))
            except Exception:
                return {}
        return {}

    if isinstance(resp, dict):
        obj = resp
    else:
        obj = _as_dict(resp)
        if not obj and hasattr(resp, "to_dict"):
            try:
                obj = resp.to_dict()
            except Exception:
                obj = {}

    status_code = int(obj.get("status_code") or getattr(resp, "status_code", 0) or 0)
    output = obj.get("output") if isinstance(obj.get("output"), dict) else _as_dict(getattr(resp, "output", {}))
    choices = output.get("choices") if isinstance(output, dict) else None
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else _as_dict(getattr(choices[0], "message", {}))
        content = msg.get("content")
        if isinstance(content, list):
            for it in content:
                # DashScope SDK sometimes returns content items as objects, not plain dicts.
                # Convert best-effort so we don't silently drop images.
                it_d: dict[str, Any]
                if isinstance(it, dict):
                    it_d = it
                else:
                    it_d = _as_dict(it)
                if not it_d:
                    continue
                if isinstance(it_d.get("text"), str):
                    text_parts.append(str(it_d["text"]))
                # image can be str/dict/list depending on SDK variant
                img_val = it_d.get("image")
                if isinstance(img_val, str):
                    images.append(img_val)
                elif isinstance(img_val, dict):
                    if isinstance(img_val.get("url"), str):
                        images.append(str(img_val["url"]))
                elif isinstance(img_val, list):
                    for elem in img_val:
                        if isinstance(elem, str):
                            images.append(elem)
                        elif isinstance(elem, dict) and isinstance(elem.get("url"), str):
                            images.append(str(elem["url"]))

                if isinstance(it_d.get("image_url"), str):
                    images.append(str(it_d["image_url"]))
                elif isinstance(it_d.get("image_url"), dict) and isinstance(it_d["image_url"].get("url"), str):
                    images.append(str(it_d["image_url"]["url"]))
                elif isinstance(it_d.get("image_url"), list):
                    for elem in it_d["image_url"]:
                        if isinstance(elem, str):
                            images.append(elem)
                        elif isinstance(elem, dict) and isinstance(elem.get("url"), str):
                            images.append(str(elem["url"]))

                b64_val = it_d.get("b64_json")
                if isinstance(b64_val, str):
                    images.append(f"data:image/png;base64,{b64_val}")
                elif isinstance(b64_val, list):
                    for elem in b64_val:
                        if isinstance(elem, str):
                            images.append(f"data:image/png;base64,{elem}")

    # fallback for variants returning output.data[{url|b64_json}]
    if not images and isinstance(output, dict):
        data = output.get("data")
        if isinstance(data, list):
            for it in data:
                it_d: dict[str, Any]
                if isinstance(it, dict):
                    it_d = it
                else:
                    it_d = _as_dict(it)
                if not it_d:
                    continue
                url_val = it_d.get("url")
                if isinstance(url_val, str):
                    images.append(url_val)
                elif isinstance(url_val, list):
                    for elem in url_val:
                        if isinstance(elem, str):
                            images.append(elem)

                b64_val = it_d.get("b64_json")
                if isinstance(b64_val, str):
                    images.append(f"data:image/png;base64,{b64_val}")
                elif isinstance(b64_val, list):
                    for elem in b64_val:
                        if isinstance(elem, str):
                            images.append(f"data:image/png;base64,{elem}")

    return "\n".join([x for x in text_parts if x]).strip(), images, str(status_code)


def _dashscope_messages(images: list[str], prompt: str) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    content: list[dict[str, Any]] = [{"image": img} for img in images]
    content.append({"text": prompt_text})
    return [{"role": "user", "content": content}]


def _http_content_blocks(images: list[str], prompt: str, *, typed: bool) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    if not typed:
        blocks: list[dict[str, Any]] = [{"image": img} for img in images]
        blocks.append({"text": prompt_text})
        return blocks
    # DashScope compatible-mode error is very explicit about `content[*].type` missing.
    # To align with DashScope's simple schema keys ({"image": ...}, {"text": ...}),
    # we keep those keys and only add the `type` discriminator.
    blocks_typed: list[dict[str, Any]] = [{"type": "image", "image": img} for img in images]
    blocks_typed.append({"type": "text", "text": prompt_text})
    return blocks_typed


def _responses_input_messages(images: list[str], prompt: str) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    content: list[dict[str, Any]] = []
    for img in images:
        s = str(img or "").strip()
        if not s:
            continue
        if s.startswith("data:") or s.startswith("http://") or s.startswith("https://"):
            content.append({"type": "input_image", "image_url": s})
    if prompt_text:
        content.append({"type": "input_text", "text": prompt_text})
    return [{"role": "user", "content": content}]


def _dashscope_typed_messages(images: list[str], prompt: str) -> list[dict[str, Any]]:
    """
    DashScope compatible-mode often requires a typed schema, where each content item has `type`.
    Example:
      {"type":"image_url","image_url":{"url":"..."}}, {"type":"text","text":"..."}
    """
    typed_blocks = _http_content_blocks(images, prompt, typed=True)
    return [{"role": "user", "content": typed_blocks}]


def _send_via_dashscope(
    *,
    images: list[str],
    prompt: str,
    model_name: str,
    api_key: str | None = None,
    base_http_api_url: str | None = None,
    force_typed_schema: bool = False,
) -> dict[str, Any]:
    try:
        import dashscope  # type: ignore
        from dashscope import MultiModalConversation  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"dashscope package unavailable: {type(e).__name__}: {e}"}

    resolved_key = (api_key or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not resolved_key:
        return {"ok": False, "error": "missing DASHSCOPE_API_KEY"}

    ds_base = (base_http_api_url or os.getenv("DASHSCOPE_BASE_HTTP_API_URL") or "").strip()
    if ds_base:
        dashscope.base_http_api_url = ds_base

    call_kwargs_base: dict[str, Any] = {
        "api_key": resolved_key,
        "model": model_name,
        "stream": False,
    }
    # Optional params compatible with user's sample
    if os.getenv("DASHSCOPE_IMAGE_N"):
        try:
            call_kwargs_base["n"] = int(os.getenv("DASHSCOPE_IMAGE_N") or "1")
        except Exception:
            pass
    if os.getenv("DASHSCOPE_IMAGE_WATERMARK"):
        call_kwargs_base["watermark"] = os.getenv("DASHSCOPE_IMAGE_WATERMARK", "false").lower() in ("1", "true", "yes")
    if os.getenv("DASHSCOPE_IMAGE_NEGATIVE_PROMPT"):
        call_kwargs_base["negative_prompt"] = os.getenv("DASHSCOPE_IMAGE_NEGATIVE_PROMPT")
    if os.getenv("DASHSCOPE_IMAGE_PROMPT_EXTEND"):
        call_kwargs_base["prompt_extend"] = os.getenv("DASHSCOPE_IMAGE_PROMPT_EXTEND", "true").lower() in ("1", "true", "yes")
    if os.getenv("DASHSCOPE_IMAGE_SIZE"):
        call_kwargs_base["size"] = os.getenv("DASHSCOPE_IMAGE_SIZE")

    def _call_with_retry(messages: list[dict[str, Any]]) -> tuple[Any | None, Exception | None]:
        retries = max(1, int(os.getenv("AIA_IMAGE_RETRIES", "3") or "3"))
        backoff_sec = float(os.getenv("AIA_IMAGE_RETRY_BACKOFF_SEC", "0.8") or "0.8")
        last_exc: Exception | None = None
        resp_obj: Any | None = None
        for attempt in range(1, retries + 1):
            try:
                kwargs = dict(call_kwargs_base)
                kwargs["messages"] = messages
                resp_obj = MultiModalConversation.call(**kwargs)
                return resp_obj, None
            except Exception as e:
                last_exc = e
                if attempt >= retries:
                    break
                time.sleep(backoff_sec * (2 ** (attempt - 1)))
        return None, last_exc

    # DashScope SDK path:
    # Compatible-mode may require typed content schema (`content[*].type`),
    # so if we detect compatible-mode, prefer typed schema directly.
    typed_msgs = _dashscope_typed_messages(images, prompt)
    simple_msgs = _dashscope_messages(images, prompt)

    first_msgs = typed_msgs if force_typed_schema else simple_msgs
    second_msgs = simple_msgs if force_typed_schema else typed_msgs

    first_schema = "typed" if first_msgs is typed_msgs else "simple"
    second_schema = "simple" if first_schema == "typed" else "typed"
    debug_first = _summarize_dashscope_messages(first_msgs)
    debug_second = _summarize_dashscope_messages(second_msgs)

    used_schema = first_schema
    used_debug = debug_first

    resp, err = _call_with_retry(first_msgs)
    if resp is None:
        # If the first schema fails without a response, try the other schema once.
        resp2, err2 = _call_with_retry(second_msgs)
        if resp2 is None:
            assert err2 is not None
            return {
                "ok": False,
                "error": (
                    f"dashscope call failed: {type(err2).__name__}: {err2} "
                    f"(debug={{first_schema={first_schema},second_schema={second_schema}}})"
                )[:900],
            }
        resp = resp2
        used_schema = second_schema
        used_debug = debug_second

    text, out_images, status = _extract_from_dashscope_response(resp)
    try:
        status_code = int(status)
    except Exception:
        status_code = 0
    if status_code and status_code != 200:
        # DashScope may return HTTP 429 (rate limit) as a non-exception status.
        # _call_with_retry only retries on exceptions, so handle 429 explicitly here.
        if status_code == 429:
            status_retries = max(1, int(os.getenv("AIA_IMAGE_STATUS_RETRIES", "4") or "4"))
            status_backoff_sec = float(os.getenv("AIA_IMAGE_STATUS_RETRY_BACKOFF_SEC", "5.0") or "5.0")
            for attempt in range(1, status_retries):
                time.sleep(status_backoff_sec * (2 ** (attempt - 1)))
                resp_retry, _err_retry = _call_with_retry(simple_msgs)
                if resp_retry is None:
                    continue
                text_r, out_images_r, status_r = _extract_from_dashscope_response(resp_retry)
                try:
                    status_r_code = int(status_r)
                except Exception:
                    status_r_code = 0
                if status_r_code == 200 or not status_r_code:
                    return {
                        "ok": True,
                        "text": text_r,
                        "images": out_images_r,
                        "backend_shape": "dashscope",
                    }
                if status_r_code == 400:
                    # If we hit schema issues after rate limit, fall back to typed once.
                    typed_msgs = _dashscope_typed_messages(images, prompt)
                    resp_t, _err_t = _call_with_retry(typed_msgs)
                    if resp_t is not None:
                        text_t, out_images_t, status_t = _extract_from_dashscope_response(resp_t)
                        try:
                            status_t_code = int(status_t)
                        except Exception:
                            status_t_code = 0
                        if status_t_code == 200 or not status_t_code:
                            return {
                                "ok": True,
                                "text": text_t,
                                "images": out_images_t,
                                "backend_shape": "dashscope",
                            }
                    # continue loop for more 429 tries
            code = getattr(resp, "code", "") or ""
            msg = getattr(resp, "message", "") or ""
            return {
                "ok": False,
                "error": (
                    f"dashscope status={status_code} code={code} debug={{used_schema={used_schema},used_debug={used_debug}}} "
                    f"message={msg[:400]} (after 429 retries)"
                ),
                "backend_shape": "dashscope",
            }

        # Compatible-mode may reject "simple" schema with HTTP 400 and a message like:
        #   messages[0].content[1].type missing required parameter.
        # To make this robust, retry typed schema whenever we see 400.
        if status_code == 400:
            resp2, _err2 = _call_with_retry(typed_msgs)
            if resp2 is not None:
                text2, out_images2, status2 = _extract_from_dashscope_response(resp2)
                try:
                    status2_code = int(status2)
                except Exception:
                    status2_code = 0
                if status2_code == 200 or not status2_code:
                    return {
                        "ok": True,
                        "text": text2,
                        "images": out_images2,
                        "backend_shape": "dashscope",
                    }

        code = getattr(resp, "code", "") or ""
        msg = getattr(resp, "message", "") or ""
        return {
            "ok": False,
            "error": (
                f"dashscope status={status_code} code={code} debug={{used_schema={used_schema},used_debug={used_debug}}} "
                f"message={msg[:400]}"
            ),
            "backend_shape": "dashscope",
        }
    return {
        "ok": True,
        "text": text,
        "images": out_images,
        "backend_shape": "dashscope",
        "debug_used_schema": used_schema,
        "debug_used_debug": used_debug,
    }


def send_image_messages(
    *,
    images: list[str],
    prompt: str,
    model: str | None = None,
    timeout_sec: int = 60,
    api_key: str | None = None,
    base_url: str | None = None,
    dashscope_api_key: str | None = None,
    dashscope_base_http_api_url: str | None = None,
) -> dict[str, Any]:
    """Send multimodal messages payload with image/text content blocks.

    Preferred payload: {"messages":[{"role":"user","content":[{"image":"..."},{"text":"..."}]}]}
    Auto-compat: try multi-image first, then fallback to single `image` field style.
    """
    model_name = (
        model
        or os.getenv("AIA_IMAGE_MODEL")
        or os.getenv("DASHSCOPE_IMAGE_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "qwen-image-2.0-pro"
    ).strip()
    resolved_base_url = (base_url or os.getenv("AIA_IMAGE_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    resolved_api_key = (api_key or os.getenv("AIA_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    resolved_ds_key = (dashscope_api_key or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    resolved_ds_base = (dashscope_base_http_api_url or os.getenv("DASHSCOPE_BASE_HTTP_API_URL") or "").strip()
    endpoint = (os.getenv("AIA_IMAGE_CHAT_ENDPOINT") or "/chat/completions").strip()
    url = _join_url(resolved_base_url, endpoint)
    if not images:
        return {"ok": False, "error": "at least one image input is required"}

    raw_selected = [str(x).strip() for x in images if str(x).strip()][:3]
    selected: list[str] = []
    input_kind: list[str] = []
    for img in raw_selected:
        if _is_data_url(img):
            selected.append(_compress_data_url_image(img))
            input_kind.append("data_url")
            continue
        if img.startswith("http://") or img.startswith("https://"):
            # Keep URL as-is when caller provides URL input.
            selected.append(img)
            input_kind.append("url")
            continue
    if not selected:
        return {"ok": False, "error": "no usable image input (expected URL or data URL)"}

    if resolved_ds_key:
        # SpecialistAgent already normalizes DashScope SDK calls to native `/api/v1`.
        # For the SDK path, prefer the official simple schema for both single and
        # multi-image requests: {"image": ...}, {"text": ...}.
        #
        # This avoids a split where multi-image succeeds but single-image still
        # trips over `messages[0].content[*].type` handling.
        ds = _send_via_dashscope(
            images=selected,
            prompt=prompt,
            model_name=model_name,
            api_key=resolved_ds_key,
            base_http_api_url=resolved_ds_base,
            force_typed_schema=False,
        )
        ds["input_kind"] = input_kind if input_kind else ["data_url"]
        # When DashScope credentials are present, always return the DashScope path result.
        # Do not silently fall through to the OpenAI-compatible HTTP path, because that can
        # mask the real SDK error with a secondary `content[*].type` error from another backend path.
        return ds

    if not resolved_api_key:
        return {"ok": False, "error": "missing api key (AIA_IMAGE_API_KEY/OPENAI_API_KEY or DASHSCOPE_API_KEY)"}
    prefer_typed_http = "compatible-mode" in resolved_base_url.lower()
    content_multi = _http_content_blocks(selected, prompt, typed=prefer_typed_http)
    content_multi_fallback = _http_content_blocks(selected, prompt, typed=not prefer_typed_http)

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    payload_multi = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_multi}],
    }
    payload_single = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_multi_fallback[-2:] if len(content_multi_fallback) >= 2 else content_multi_fallback}],
    }
    responses_payload = {
        "model": model_name,
        "input": {"messages": _responses_input_messages(selected, prompt)},
    }

    with httpx.Client(timeout=float(timeout_sec)) as client:
        # try multi-image payload first
        try:
            r = _post_with_retry(client, url=url, headers=headers, payload=payload_multi)
        except Exception as e:
            return {"ok": False, "error": f"http request failed: {type(e).__name__}: {e}", "backend_shape": "multi"}
        if r.status_code >= 400:
            # fallback single-image shape for strict backends
            try:
                r2 = _post_with_retry(client, url=url, headers=headers, payload=payload_single)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"http fallback request failed: {type(e).__name__}: {e}",
                    "backend_shape": "single-fallback-failed",
                }
            if r2.status_code >= 400:
                body2 = str(r2.text or "")
                if ("input.messages" in body2) or ("Input should be 'user'" in body2):
                    # OpenAI-compatible Responses schema fallback.
                    try:
                        r3 = _post_with_retry(
                            client,
                            url=_join_url(resolved_base_url, "/responses"),
                            headers=headers,
                            payload=responses_payload,
                        )
                        if r3.status_code < 400:
                            obj3 = r3.json()
                            text3, out_images3 = _extract_text_and_images(obj3 if isinstance(obj3, dict) else {})
                            return {
                                "ok": True,
                                "text": text3,
                                "images": out_images3,
                                "backend_shape": "responses-fallback",
                                "input_kind": input_kind if input_kind else ["data_url"],
                            }
                    except Exception:
                        pass
                return {
                    "ok": False,
                    "error": f"http {r2.status_code}: {r2.text[:500]}",
                    "backend_shape": "single-fallback-failed",
                }
            try:
                obj2 = r2.json()
            except Exception:
                return {"ok": False, "error": f"non-json response: {r2.text[:500]}", "backend_shape": "single"}
            text, out_images = _extract_text_and_images(obj2 if isinstance(obj2, dict) else {})
            return {
                "ok": True,
                "text": text,
                "images": out_images,
                "backend_shape": "single",
                "input_kind": input_kind[-1:] if input_kind else ["data_url"],
            }

        try:
            obj = r.json()
        except Exception:
            return {"ok": False, "error": f"non-json response: {r.text[:500]}", "backend_shape": "multi"}
        text, out_images = _extract_text_and_images(obj if isinstance(obj, dict) else {})
        return {
            "ok": True,
            "text": text,
            "images": out_images,
            "backend_shape": "multi",
            "input_kind": input_kind if input_kind else ["data_url"],
        }


__all__ = ["send_image_messages"]

