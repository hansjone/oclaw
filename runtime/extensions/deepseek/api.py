from __future__ import annotations

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_CATALOG = (
    {"id": "deepseek-chat", "name": "DeepSeek Chat", "reasoning": False},
    {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "reasoning": True},
)


def build_deepseek_model_definition(model: dict) -> dict:
    out = dict(model)
    out["api"] = "openai-completions"
    return out


def build_deepseek_provider() -> dict:
    return {
        "base_url": DEEPSEEK_BASE_URL,
        "api": "openai-completions",
        "models": [build_deepseek_model_definition(m) for m in DEEPSEEK_MODEL_CATALOG],
    }
