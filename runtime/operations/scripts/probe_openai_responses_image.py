#!/usr/bin/env python3
"""POST minimal vision payloads to an OpenAI-compatible ``/responses`` endpoint.

Run locally: loads ``oclaw/_local/system.env`` the same way the gateway does, then POSTs variants.

Example::

    set OPENAI_BASE_URL=https://...
    set OPENAI_API_KEY=sk-...
    set OPENAI_MODEL=qwen-vl-plus
    python runtime/operations/scripts/probe_openai_responses_image.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Same bootstrap as gateway: ``interfaces/http/fastapi_app.py`` calls ``load_system_env()`` so
# ``oclaw/_local/system.env`` is merged before reading ``OPENAI_*``.
try:
    from svc.config.bootstrap_env import load_system_env

    load_system_env()
except ImportError:
    pass

try:
    import httpx
except ImportError:
    print("install httpx: pip install httpx", file=sys.stderr)
    raise SystemExit(2)

# 1x1 transparent PNG
_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _variants(model: str, data_uri: str) -> list[tuple[str, dict]]:
    user_block_resp = {
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": "What color is this pixel image? One word."},
            {"type": "input_image", "image_url": data_uri, "detail": "auto"},
        ],
    }
    user_plain_resp = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "What color is this pixel image? One word."},
            {"type": "input_image", "image_url": data_uri, "detail": "auto"},
        ],
    }
    user_chat = {
        "role": "user",
        "content": [
            {"type": "text", "text": "What color is this pixel image? One word."},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ],
    }
    return [
        ("flat_resp_envelope", {"model": model, "input": [user_block_resp]}),
        ("flat_resp_plain", {"model": model, "input": [user_plain_resp]}),
        ("nested_messages_resp_env", {"model": model, "input": {"messages": [user_block_resp]}}),
        ("nested_messages_resp_plain", {"model": model, "input": {"messages": [user_plain_resp]}}),
        ("nested_messages_chat", {"model": model, "input": {"messages": [user_chat]}}),
    ]


def main() -> None:
    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    if not key:
        print("OPENAI_API_KEY is required", file=sys.stderr)
        raise SystemExit(2)

    url = f"{base}/responses"
    data_uri = f"data:image/png;base64,{_PNG_B64}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    print(f"POST {url}", flush=True)
    for label, body in _variants(model, data_uri):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=120.0)
        except httpx.HTTPError as exc:
            print(f"\n=== {label} transport_error {exc}", flush=True)
            continue
        tail = (r.text or "")[:2400]
        print(f"\n=== {label} status={r.status_code}", flush=True)
        print(tail, flush=True)
        if r.status_code < 400:
            print("(first successful variant — use this shape for your gateway)", flush=True)
            break


if __name__ == "__main__":
    main()
