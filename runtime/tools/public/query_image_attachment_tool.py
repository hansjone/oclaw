from __future__ import annotations

from typing import Any

from oclaw.platform.files.attachment_assets import attachment_id_to_data_url
from oclaw.platform.llm.image_message_client import send_image_messages
from oclaw.runtime.tools.base import ToolSpec


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
        prompt = (
            (
                "请详细描述这张图片的主要内容、对象、场景和可见文字。"
                "回答请使用要点列表，避免臆测。"
            )
            if task == "describe"
            else (
                "请只提取图片中可见文字并按阅读顺序输出。"
                "如果有表格，保持行列结构；不确定的内容标注为[unclear]。"
            )
        )
        if question:
            prompt = f"{prompt}\n\n用户问题：{question}"
        out = send_image_messages(images=[data_url], prompt=prompt)
        if not bool(out.get("ok")):
            return {
                "ok": False,
                "error": str(out.get("error") or "image_query_failed"),
                "task": task,
                "attachment_id": attachment_id,
            }
        text = str(out.get("text") or "")
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
