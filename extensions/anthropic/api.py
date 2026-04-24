from __future__ import annotations

from typing import Any, Callable


CLAUDE_CLI_BACKEND_ID = "claude-cli"


def is_claude_cli_provider(provider_id: str) -> bool:
    return str(provider_id or "").strip().lower() == CLAUDE_CLI_BACKEND_ID


def build_anthropic_provider(_api=None) -> dict:
    return {
        "id": "anthropic",
        "label": "Anthropic",
        "docs_path": "/providers/models",
        "hook_aliases": [CLAUDE_CLI_BACKEND_ID],
        "env_vars": ["ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"],
        # NOTE: Full auth, cli-backend, replay-policy, and stream wrappers are not ported yet.
    }


def _parse_header_list(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _is_anthropic_oauth_api_key(api_key: Any) -> bool:
    return isinstance(api_key, str) and "sk-ant-oat" in api_key


def _merge_anthropic_beta_header(headers: dict[str, str] | None, betas: list[str]) -> dict[str, str]:
    merged = dict(headers or {})
    existing_key = next((k for k in merged if str(k).lower() == "anthropic-beta"), None)
    existing = _parse_header_list(merged.get(existing_key, "")) if existing_key else []
    all_values = list(dict.fromkeys([*existing, *betas]))
    merged[existing_key or "anthropic-beta"] = ",".join(all_values)
    return merged


def resolve_anthropic_betas(extra_params: dict | None, model_id: str) -> list[str] | None:
    extra_params = extra_params or {}
    out: list[str] = []
    configured = extra_params.get("anthropicBeta")
    if isinstance(configured, str) and configured.strip():
        out.append(configured.strip())
    elif isinstance(configured, list):
        out.extend([str(x).strip() for x in configured if str(x).strip()])
    if extra_params.get("context1m") is True and str(model_id).lower().startswith(
        ("claude-opus-4", "claude-sonnet-4")
    ):
        out.append("context-1m-2025-08-07")
    out = list(dict.fromkeys(out))
    return out or None


def create_anthropic_beta_headers_wrapper(base_stream_fn: Callable | None, betas: list[str]) -> Callable:
    underlying = base_stream_fn or (lambda model, context, options=None: {"model": model, "context": context, "options": options or {}})
    pi_defaults = ["fine-grained-tool-streaming-2025-05-14", "interleaved-thinking-2025-05-14"]
    pi_oauth = ["claude-code-20250219", "oauth-2025-04-20", *pi_defaults]

    def wrapped(model, context, options=None):
        opts = dict(options or {})
        is_oauth = _is_anthropic_oauth_api_key(opts.get("apiKey"))
        requested_context1m = "context-1m-2025-08-07" in betas
        effective_betas = [b for b in betas if not (is_oauth and requested_context1m and b == "context-1m-2025-08-07")]
        all_betas = list(dict.fromkeys([*(pi_oauth if is_oauth else pi_defaults), *effective_betas]))
        opts["headers"] = _merge_anthropic_beta_header(opts.get("headers"), all_betas)
        return underlying(model, context, opts)

    return wrapped


def _normalize_fast_mode(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key in {"off", "false", "no", "0", "disable", "disabled", "normal"}:
        return False
    if key in {"on", "true", "yes", "1", "enable", "enabled", "fast"}:
        return True
    return None


def resolve_anthropic_fast_mode(extra_params: dict | None) -> bool | None:
    extra_params = extra_params or {}
    return _normalize_fast_mode(extra_params.get("fastMode", extra_params.get("fast_mode")))


def resolve_anthropic_service_tier(extra_params: dict | None) -> str | None:
    extra_params = extra_params or {}
    raw = extra_params.get("serviceTier", extra_params.get("service_tier"))
    if isinstance(raw, str):
        norm = raw.strip().lower()
        if norm in {"auto", "standard_only"}:
            return norm
    return None


def create_anthropic_fast_mode_wrapper(base_stream_fn: Callable | None, enabled: bool) -> Callable:
    underlying = base_stream_fn or (lambda model, context, options=None: {"model": model, "context": context, "options": options or {}})

    def wrapped(model, context, options=None):
        opts = dict(options or {})
        if _is_anthropic_oauth_api_key(opts.get("apiKey")):
            return underlying(model, context, opts)
        payload = dict(opts.get("payload") or {})
        payload["service_tier"] = "auto" if enabled else "standard_only"
        opts["payload"] = payload
        return underlying(model, context, opts)

    return wrapped


def create_anthropic_service_tier_wrapper(base_stream_fn: Callable | None, service_tier: str) -> Callable:
    underlying = base_stream_fn or (lambda model, context, options=None: {"model": model, "context": context, "options": options or {}})

    def wrapped(model, context, options=None):
        opts = dict(options or {})
        if _is_anthropic_oauth_api_key(opts.get("apiKey")):
            return underlying(model, context, opts)
        payload = dict(opts.get("payload") or {})
        payload["service_tier"] = service_tier
        opts["payload"] = payload
        return underlying(model, context, opts)

    return wrapped


def wrap_anthropic_provider_stream(ctx: dict) -> Callable | None:
    stream_fn = ctx.get("streamFn")
    model_id = str(ctx.get("modelId") or "")
    extra_params = ctx.get("extraParams") or {}

    betas = resolve_anthropic_betas(extra_params, model_id)
    service_tier = resolve_anthropic_service_tier(extra_params)
    fast_mode = resolve_anthropic_fast_mode(extra_params)

    wrapped = stream_fn
    if betas:
        wrapped = create_anthropic_beta_headers_wrapper(wrapped, betas)
    if service_tier:
        wrapped = create_anthropic_service_tier_wrapper(wrapped, service_tier)
    if fast_mode is not None:
        wrapped = create_anthropic_fast_mode_wrapper(wrapped, fast_mode)
    return wrapped
