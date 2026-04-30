from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.platform.files.text_attachment_store import (
    DEFAULT_TEXT_CHUNK_OVERLAP,
    DEFAULT_TEXT_CHUNK_SIZE,
    save_text_document,
)
from oclaw.runtime.extensions.openai.api import OPENAI_DEFAULT_AUDIO_TRANSCRIPTION_MODEL
from oclaw.runtime.tools.base import ToolSpec


def _ffmpeg_exists() -> bool:
    try:
        p = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=3)
        return p.returncode == 0
    except Exception:
        return False


def _ffprobe_json(path: Path) -> dict[str, Any] | None:
    try:
        p = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if p.returncode != 0:
            return None
        obj = json.loads(p.stdout or "{}")
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _safe_int(raw: Any, default: int, *, min_value: int = 1, max_value: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < min_value:
        return default
    return min(value, max_value)


def _oclaw_config_path() -> Path:
    raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else p.resolve()
    return Path(__file__).resolve().parents[4] / "oclaw.json"


def _video_transcript_chunk_defaults() -> tuple[int, int]:
    size = DEFAULT_TEXT_CHUNK_SIZE
    overlap = DEFAULT_TEXT_CHUNK_OVERLAP
    try:
        cfg_path = _oclaw_config_path()
        if cfg_path.exists() and cfg_path.is_file():
            obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            tab = (
                (((obj.get("plugins") or {}).get("entries") or {}).get("memory-wiki") or {})
                .get("auto", {})
                .get("attachments", {})
                .get("tabular", {})
            )
            if isinstance(tab, dict):
                size = _safe_int(tab.get("video_transcript_chunk_size"), size, min_value=200, max_value=8_000)
                overlap = _safe_int(tab.get("video_transcript_chunk_overlap"), overlap, min_value=0, max_value=4_000)
    except Exception:
        pass
    overlap = max(0, min(overlap, max(0, size - 1)))
    return size, overlap


def _normalized_video_meta(ffprobe_obj: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(ffprobe_obj, dict):
        return out
    fmt = ffprobe_obj.get("format") if isinstance(ffprobe_obj.get("format"), dict) else {}
    streams = ffprobe_obj.get("streams") if isinstance(ffprobe_obj.get("streams"), list) else []
    if isinstance(fmt, dict) and fmt.get("duration") is not None:
        try:
            out["duration_sec"] = float(fmt.get("duration"))
        except Exception:
            pass
    for s in streams:
        if not isinstance(s, dict):
            continue
        if str(s.get("codec_type") or "") != "video":
            continue
        try:
            if s.get("width") is not None:
                out["width"] = int(s.get("width"))
            if s.get("height") is not None:
                out["height"] = int(s.get("height"))
        except Exception:
            pass
        fr = str(s.get("avg_frame_rate") or s.get("r_frame_rate") or "").strip()
        if fr and fr != "0/0" and "/" in fr:
            try:
                a, b = fr.split("/", 1)
                fa = float(a)
                fb = float(b)
                if fb:
                    out["fps"] = fa / fb
            except Exception:
                pass
        break
    return out


def query_video_attachment_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(args.get("attachment_id") or "").strip()
        task = str(args.get("task") or "meta").strip().lower()
        lang = str(args.get("lang") or "").strip().lower()
        if not attachment_id:
            return {"ok": False, "error": "attachment_id_required"}
        if task not in {"meta", "transcript"}:
            return {"ok": False, "error": "invalid_task"}

        store = AttachmentAssetStore()
        p = store.get_local_path(attachment_id)
        meta = store.get_meta(attachment_id)
        if p is None:
            return {"ok": False, "error": "attachment_not_found"}

        if task == "meta":
            fp = _ffprobe_json(p)
            norm = _normalized_video_meta(fp)
            return {
                "ok": True,
                "task": "meta",
                "attachment_id": attachment_id,
                "name": (meta.name if meta else p.name),
                "mime": (meta.mime if meta else "video/*"),
                "bytes": int(meta.bytes if meta else (p.stat().st_size if p.exists() else 0)),
                "duration_sec": norm.get("duration_sec"),
                "width": norm.get("width"),
                "height": norm.get("height"),
                "fps": norm.get("fps"),
                "ffprobe": fp if fp else None,
                "note": "Use task=transcript to extract audio transcript (requires ffmpeg + OpenAI key).",
            }

        if not _ffmpeg_exists():
            return {
                "ok": False,
                "error": "ffmpeg_missing",
                "hint": "Install ffmpeg (ffmpeg/ffprobe on PATH) to enable transcript extraction.",
            }
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return {"ok": False, "error": "OPENAI_API_KEY_missing"}

        try:
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "audio.wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if not wav.exists() or wav.stat().st_size <= 0:
                    return {"ok": False, "error": "audio_extract_failed"}
                try:
                    from openai import OpenAI
                except Exception as e:
                    return {"ok": False, "error": f"openai_package_missing: {type(e).__name__}: {e}"}

                base_url = str(os.getenv("OPENAI_BASE_URL") or "").strip()
                client_kwargs: dict[str, Any] = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                client = OpenAI(**client_kwargs)

                model = str(args.get("model") or os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL") or OPENAI_DEFAULT_AUDIO_TRANSCRIPTION_MODEL).strip()
                prompt = str(args.get("prompt") or "").strip()
                wav_bytes = wav.read_bytes()
                f = io.BytesIO(wav_bytes)
                f.name = "audio.wav"  # type: ignore[attr-defined]
                try:
                    resp = client.audio.transcriptions.create(  # type: ignore[attr-defined]
                        model=model,
                        file=f,
                        **({"prompt": prompt} if prompt else {}),
                    )
                    text = str(getattr(resp, "text", "") or "")
                except Exception as e:
                    return {"ok": False, "error": f"transcription_failed: {type(e).__name__}: {e}"}

                if not text.strip():
                    return {"ok": False, "error": "empty_transcript"}

                name = str(meta.name if meta else p.name)
                text_name = f"{name}.transcript.txt"
                cfg_chunk_size, cfg_chunk_overlap = _video_transcript_chunk_defaults()
                chunk_size = int(args.get("chunk_size") or cfg_chunk_size)
                chunk_overlap = int(args.get("chunk_overlap") or cfg_chunk_overlap)
                text_meta = save_text_document(
                    attachment_id=str(attachment_id),
                    name=text_name,
                    text=text,
                    source_kind="video_transcript",
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                preview = text[:1200]
                note = (
                    "Use query_text_attachment(text_id=...) to retrieve exact evidence with offsets."
                    if lang.startswith("en")
                    else "后续请用 query_text_attachment(text_id=...) 按需检索证据（支持 offset/top_k/关键词）。"
                )
                return {
                    "ok": True,
                    "task": "transcript",
                    "attachment_id": attachment_id,
                    "name": text_name,
                    "text_id": str(text_meta.get("text_id") or ""),
                    "chars": int(text_meta.get("chars") or 0),
                    "chunks": int(text_meta.get("chunks") or 0),
                    "preview": preview,
                    "note": note,
                }
        except Exception as e:
            return {"ok": False, "error": f"transcript_failed: {type(e).__name__}: {e}"}

    return ToolSpec(
        name="query_video_attachment",
        description="Query a video attachment by attachment_id (meta or transcript).",
        parameters={
            "type": "object",
            "properties": {
                "attachment_id": {"type": "string"},
                "task": {"type": "string", "enum": ["meta", "transcript"]},
                "lang": {"type": "string", "description": "Optional hint: zh/en."},
                "model": {"type": "string", "description": "Optional transcription model override."},
                "prompt": {"type": "string", "description": "Optional transcription prompt/context."},
                "chunk_size": {"type": "integer", "description": "Transcript chunk size (chars)."},
                "chunk_overlap": {"type": "integer", "description": "Transcript chunk overlap (chars)."},
            },
            "required": ["attachment_id"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
        tags=frozenset({"video", "read"}),
    )


__all__ = ["query_video_attachment_tool"]
