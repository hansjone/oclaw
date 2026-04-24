from __future__ import annotations

QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL_ID = "qwen3.5-plus"
QWEN_DEFAULT_MODEL_REF = f"qwen/{QWEN_DEFAULT_MODEL_ID}"
QWEN_36_PLUS_MODEL_ID = "qwen3.6-plus"
MODELSTUDIO_BASE_URL = QWEN_BASE_URL


def is_qwen_coding_plan_base_url(base_url: str | None) -> bool:
    v = str(base_url or "").lower()
    return "coding." in v


def build_qwen_provider(*, base_url: str | None = None) -> dict:
    return {
        "id": "qwen",
        "base_url": base_url or QWEN_BASE_URL,
        "default_model": QWEN_DEFAULT_MODEL_ID,
    }


def build_modelstudio_provider(*, base_url: str | None = None) -> dict:
    return {
        "id": "modelstudio",
        "base_url": base_url or MODELSTUDIO_BASE_URL,
        "default_model": QWEN_DEFAULT_MODEL_ID,
    }


def apply_qwen_native_streaming_usage_compat(provider_config: dict) -> dict:
    return dict(provider_config or {})
