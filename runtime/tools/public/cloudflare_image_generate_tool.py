from __future__ import annotations

import base64
import io
import json
import os
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from PIL import Image

from svc.files.attachment_assets import AttachmentAssetStore
from runtime.operations.mcp_env import apply_gateway_mcp_env_to_os
from runtime.tools.base import ToolSpec


def _to_image_bytes(resp_body: bytes, content_type: str) -> tuple[bytes, str]:
    ct = str(content_type or "").lower()
    if ct.startswith("image/"):
        return resp_body, ct.split(";", 1)[0].strip()
    obj = json.loads(resp_body.decode("utf-8", errors="ignore"))
    if not isinstance(obj, dict):
        raise ValueError("invalid_cloudflare_response")
    if obj.get("success") is False:
        raise ValueError(json.dumps(obj, ensure_ascii=False))
    result = obj.get("result")
    if isinstance(result, dict):
        b64 = str(result.get("image") or result.get("b64_json") or "").strip()
        if b64.startswith("data:") and ";base64," in b64:
            head, _, payload = b64.partition(",")
            mime = head.split(":", 1)[-1].split(";", 1)[0].strip() or "image/png"
            return base64.b64decode(payload.encode("ascii")), mime
        if b64:
            return base64.b64decode(b64.encode("ascii")), "image/png"
    raise ValueError("cloudflare_response_has_no_image")


def cloudflare_image_generate_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        apply_gateway_mcp_env_to_os()
        account_id = str(args.get("account_id") or os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
        api_token = str(args.get("api_token") or os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
        model = str(args.get("model") or "@cf/stabilityai/stable-diffusion-xl-base-1.0").strip()
        prompt = str(args.get("prompt") or "").strip()
        options = args.get("options") if isinstance(args.get("options"), dict) else {}
        if not account_id:
            return {"ok": False, "error": "missing CLOUDFLARE_ACCOUNT_ID (or account_id argument)"}
        if not api_token:
            return {"ok": False, "error": "missing CLOUDFLARE_API_TOKEN (or api_token argument)"}
        if not prompt:
            return {"ok": False, "error": "prompt is required"}
        endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        payload = {"prompt": prompt}
        payload.update(options)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "image/*,application/json",
            },
        )
        try:
            with urllib_request.urlopen(req, timeout=45) as resp:
                raw = resp.read()
                ct = str(resp.headers.get("content-type") or "")
        except urllib_error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                err_body = ""
            return {"ok": False, "error": f"cloudflare_http_{exc.code}: {err_body[:500]}"}
        except Exception as exc:
            return {"ok": False, "error": f"cloudflare_request_failed: {type(exc).__name__}: {exc}"}

        try:
            image_bytes, mime = _to_image_bytes(raw, ct)
        except Exception as exc:
            return {"ok": False, "error": f"cloudflare_decode_failed: {type(exc).__name__}: {exc}"}

        width = None
        height = None
        try:
            with Image.open(io.BytesIO(image_bytes)) as im:
                width, height = im.size
        except Exception:
            pass

        store = AttachmentAssetStore()
        ext = ".png" if "png" in mime.lower() else ".jpg"
        meta = store.save_bytes(
            image_bytes,
            filename=f"cloudflare-generated{ext}",
            mime=mime or "image/png",
            width=width,
            height=height,
        )
        return {
            "ok": True,
            "provider": "cloudflare_direct",
            "model": model,
            "attachment_id": meta.attachment_id,
            "name": meta.name,
            "mime": meta.mime,
            "bytes": meta.bytes,
            "width": meta.width,
            "height": meta.height,
        }

    return ToolSpec(
        name="cloudflare_image_generate",
        description="Generate image by direct Cloudflare Workers AI REST (bypass Cloudflare MCP).",
        parameters={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image prompt text."},
                "model": {"type": "string", "description": "Workers AI model id."},
                "options": {"type": "object", "description": "Extra model options merged into request body."},
                "account_id": {"type": "string", "description": "Optional override for CLOUDFLARE_ACCOUNT_ID."},
                "api_token": {"type": "string", "description": "Optional override for CLOUDFLARE_API_TOKEN."},
            },
            "required": ["prompt"],
        },
        handler=handler,
        tags=frozenset({"image", "cloudflare", "generation"}),
        risk_level="low",
        timeout_s=60.0,
    )


__all__ = ["cloudflare_image_generate_tool", "_to_image_bytes"]

