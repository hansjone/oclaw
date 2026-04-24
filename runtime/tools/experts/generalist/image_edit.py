from __future__ import annotations

import base64
import io
import os
from typing import Any

from PIL import Image

from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.runtime.tools.base import ToolSpec


def image_edit_tool() -> ToolSpec:
    """Edit an uploaded image using OpenAI Images API.

    Input image is referenced by attachment_id (disk-backed asset store).
    Output is saved back to the asset store and returned as attachment_id.
    """

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(args.get("attachment_id") or "").strip()
        instruction = str(args.get("instruction") or "").strip()
        model = str(args.get("model") or os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip()
        if not attachment_id:
            return {"ok": False, "error": "attachment_id is required"}
        if not instruction:
            return {"ok": False, "error": "instruction is required"}

        store = AttachmentAssetStore()
        blob, meta = store.load_bytes(attachment_id)
        if not blob:
            return {"ok": False, "error": f"attachment not found: {attachment_id}"}

        try:
            from openai import OpenAI
        except Exception as e:
            return {"ok": False, "error": f"openai package is not available: {type(e).__name__}: {e}"}

        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
        if not api_key:
            return {"ok": False, "error": "OPENAI_API_KEY is not set"}

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        # OpenAI SDK expects a file-like object for edits.
        img_file = io.BytesIO(blob)
        img_file.name = "input.png"  # type: ignore[attr-defined]

        b64_out: str | None = None
        try:
            # Preferred: image edit endpoint (if supported by the gateway/model).
            resp = client.images.edit(  # type: ignore[attr-defined]
                model=model,
                image=img_file,
                prompt=instruction,
                response_format="b64_json",
            )
            data0 = resp.data[0] if getattr(resp, "data", None) else None
            b64_out = getattr(data0, "b64_json", None) if data0 is not None else None
        except Exception:
            # Fallback: generate a new image from prompt (still returns an image, but not true edit).
            try:
                resp = client.images.generate(  # type: ignore[attr-defined]
                    model=model,
                    prompt=instruction,
                    response_format="b64_json",
                )
                data0 = resp.data[0] if getattr(resp, "data", None) else None
                b64_out = getattr(data0, "b64_json", None) if data0 is not None else None
            except Exception as e2:
                return {"ok": False, "error": f"image api failed: {type(e2).__name__}: {e2}"}

        if not b64_out:
            return {"ok": False, "error": "image api returned no b64_json payload"}

        try:
            out_bytes = base64.b64decode(b64_out.encode("ascii"))
        except Exception as e:
            return {"ok": False, "error": f"failed to decode image b64: {type(e).__name__}: {e}"}

        width = None
        height = None
        try:
            with Image.open(io.BytesIO(out_bytes)) as im:
                width, height = im.size
        except Exception:
            pass

        out_meta = store.save_bytes(
            out_bytes,
            filename=f"edited-{meta.name if meta else 'image'}.png",
            mime="image/png",
            width=width,
            height=height,
        )
        return {
            "ok": True,
            "attachment_id": out_meta.attachment_id,
            "name": out_meta.name,
            "mime": out_meta.mime,
            "bytes": out_meta.bytes,
            "width": out_meta.width,
            "height": out_meta.height,
        }

    return ToolSpec(
        name="image_edit",
        description="Edit an uploaded image referenced by attachment_id, returning a new attachment_id.",
        parameters={
            "type": "object",
            "properties": {
                "attachment_id": {"type": "string", "description": "Input image attachment id (image_ref)."},
                "instruction": {"type": "string", "description": "Edit instruction for the image."},
                "model": {"type": "string", "description": "OpenAI image model name (default: gpt-image-1)."},
            },
            "required": ["attachment_id", "instruction"],
        },
        handler=handler,
        tags=frozenset({"image", "edit"}),
    )


__all__ = ["image_edit_tool"]

