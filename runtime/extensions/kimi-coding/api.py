from __future__ import annotations

KIMI_CODING_BASE_URL = "https://api.moonshot.ai"
KIMI_CODING_DEFAULT_MODEL_ID = "kimi-k2.5"
KIMI_CODING_MODEL_REF = "kimi/kimi-k2.5"
KIMI_MODEL_REF = KIMI_CODING_MODEL_REF


def build_kimi_coding_provider() -> dict:
    return {
        "id": "kimi",
        "base_url": KIMI_CODING_BASE_URL,
        "default_model": KIMI_CODING_DEFAULT_MODEL_ID,
    }
