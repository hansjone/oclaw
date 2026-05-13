from __future__ import annotations

from typing import Any

from svc.files.attachment_assets import attachment_id_to_data_url
from svc.llm.image_ocr_client import (
    VISION_DESCRIBE_PROMPT_ZH,
    VISION_OCR_EXTRACT_PROMPT_ZH,
    send_ocr_image_messages,
    vision_llm_backend_status,
)
from runtime.tools.base import ToolSpec


def query_image_attachment_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(args.get("attachment_id") or "").strip()
        if not attachment_id:
            return {"ok": False, "error": "attachment_id_required"}
        task = str(args.get("task") or "describe").strip().lower()
        question = str(args.get("question") or "").strip()
        if task not in {"describe", "ocr"}:
            return {"ok": False, "error": "invalid_task"}
        data_url = attachment_id_to_data_url(attachment_id=attachment_id)
        if not data_url:
            return {"ok": False, "error": "attachment_not_found"}
        vs = vision_llm_backend_status()
        if not bool(vs.get("ok")):
            return {
                "ok": False,
                "error": "vision_backend_not_configured",
                "hint": str(vs.get("hint_zh") or vs.get("hint_en") or "").strip(),
                "hint_en": str(vs.get("hint_en") or "").strip(),
                "task": task,
                "attachment_id": attachment_id,
            }
        prompt = VISION_DESCRIBE_PROMPT_ZH if task == "describe" else VISION_OCR_EXTRACT_PROMPT_ZH
        if question:
            prompt = f"{prompt}\n\n用户问题：{question}"
        out = send_ocr_image_messages(images=[data_url], prompt=prompt)
        if not bool(out.get("ok")):
            return {
                "ok": False,
                "error": str(out.get("error") or "image_query_failed"),
                "task": task,
                "attachment_id": attachment_id,
            }
        text = str(out.get("text") or "")
        if not str(text).strip():
            return {
                "ok": False,
                "error": "empty_image_analysis_response",
                "hint": (
                    "Vision backend returned status ok but no text. Set AIA_OCR_MODEL to a vision-capable id "
                    "for your gateway, or check rate limits (HTTP 429)."
                ),
                "task": task,
                "attachment_id": attachment_id,
                "backend_shape": str(out.get("backend_shape") or ""),
            }
        if len(text) > 12_000:
            text = text[:12_000] + "\n\n...[truncated image analysis output]"
        return {
            "ok": True,
            "task": task,
            "attachment_id": attachment_id,
            "text": text,
            "input_kind": list(out.get("input_kind") or []),
            "backend_shape": str(out.get("backend_shape") or ""),
        }

    return ToolSpec(
        name="query_image_attachment",
        description="Analyze an uploaded image by attachment_id (describe or OCR).",
        parameters={
            "type": "object",
            "properties": {
                "attachment_id": {"type": "string"},
                "task": {"type": "string", "enum": ["describe", "ocr"]},
                "question": {"type": "string"},
            },
            "required": ["attachment_id"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
        tags=frozenset({"image", "read"}),
    )


__all__ = ["query_image_attachment_tool"]
