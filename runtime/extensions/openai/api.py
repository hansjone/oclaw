from __future__ import annotations
import re

OPENAI_DEFAULT_MODEL = "openai/gpt-4.1"
OPENAI_CODEX_DEFAULT_MODEL = "openai/codex-mini-latest"
OPENAI_DEFAULT_IMAGE_MODEL = "gpt-image-1"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
OPENAI_DEFAULT_AUDIO_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
OPENAI_DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_DEFAULT_TTS_VOICE = "alloy"


def apply_openai_config(cfg: dict) -> dict:
    return dict(cfg or {})


def apply_openai_provider_config(cfg: dict) -> dict:
    return dict(cfg or {})


def build_openai_provider() -> dict:
    return {
        "id": "openai",
        "label": "OpenAI",
        "api": "openai-responses",
        "base_url": "https://api.openai.com/v1",
        "default_model": OPENAI_DEFAULT_MODEL,
    }


def build_openai_codex_provider() -> dict:
    return {
        "id": "openai-codex",
        "label": "OpenAI Codex",
        "api": "openai-responses",
        "base_url": "https://chatgpt.com/backend-api",
        "default_model": OPENAI_CODEX_DEFAULT_MODEL,
    }


def build_openai_image_generation_provider() -> dict:
    def _generate(*, prompt: str, size: str | None = None, quality: str | None = None, **_kwargs):
        return {
            "model": OPENAI_DEFAULT_IMAGE_MODEL,
            "prompt": prompt,
            **({"size": size} if size else {}),
            **({"quality": quality} if quality else {}),
        }

    return {
        "id": "openai",
        "label": "OpenAI Images",
        "model": OPENAI_DEFAULT_IMAGE_MODEL,
        "generate": _generate,
    }


def is_openai_api_base_url(base_url: str | None = None) -> bool:
    trimmed = str(base_url or "").strip()
    if not trimmed:
        return False
    return bool(re.fullmatch(r"https?://api\.openai\.com(?:/v1)?/?", trimmed, re.I))


def is_openai_codex_base_url(base_url: str | None = None) -> bool:
    trimmed = str(base_url or "").strip()
    if not trimmed:
        return False
    return bool(re.fullmatch(r"https?://chatgpt\.com/backend-api(?:/v1)?/?", trimmed, re.I))
