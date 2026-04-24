from __future__ import annotations

import json
from typing import Any

from oclaw.runtime.skill_installer import (
    create_skill_from_template,
    install_skill_from_local_dir,
    install_skill_from_registry_archive,
    list_skills_with_status,
    set_skill_enabled,
)
from oclaw.runtime.skills import discover_workspace_skill_manifests, load_skill_manifest

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _normalize_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return None


def _get_store(context: Any) -> Any | None:
    if isinstance(context, dict) and context.get("store") is not None:
        return context.get("store")
    return None


def _skills_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    store = _get_store(context)
    if store is None:
        _unavailable(respond, "skills.status requires context.store")
        return
    _ok(respond, {"skills": list_skills_with_status(store=store)})


def _skills_bins_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    bins: set[str] = set()
    for m in discover_workspace_skill_manifests():
        oc = dict(m.metadata_oclaw or {})
        req = oc.get("requires")
        if isinstance(req, dict):
            for k in ("bins", "anyBins"):
                raw = req.get(k)
                if isinstance(raw, list):
                    for it in raw:
                        v = _normalize_optional_str(it)
                        if v:
                            bins.add(v)
        for spec in m.install:
            payload = dict(spec.payload or {})
            raw_bins = payload.get("bins")
            if isinstance(raw_bins, list):
                for it in raw_bins:
                    v = _normalize_optional_str(it)
                    if v:
                        bins.add(v)
    _ok(respond, {"bins": sorted(bins, key=lambda x: x.lower())})


def _skills_search_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid skills.search params")
        return
    query = _normalize_optional_str(params.get("query")) or ""
    limit = params.get("limit")
    limit_n = int(limit) if isinstance(limit, int) and limit > 0 else 20
    hook = context.get("search_clawhub_skills") if isinstance(context, dict) else None
    if callable(hook):
        try:
            results = hook({"query": query, "limit": limit_n})
            _ok(respond, {"results": results if isinstance(results, list) else []})
        except Exception as exc:
            _unavailable(respond, str(exc))
        return
    out: list[dict[str, Any]] = []
    for m in discover_workspace_skill_manifests():
        hay = f"{m.name}\n{m.description}\n{m.body}".lower()
        if query.lower() in hay:
            out.append({"slug": m.name, "name": m.name, "description": m.description, "source": "local"})
        if len(out) >= limit_n:
            break
    _ok(respond, {"results": out})


def _skills_detail_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid skills.detail params")
        return
    slug = _normalize_optional_str(params.get("slug"))
    if not slug:
        _bad(respond, "invalid skills.detail params: slug required")
        return
    hook = context.get("fetch_clawhub_skill_detail") if isinstance(context, dict) else None
    if callable(hook):
        try:
            detail = hook({"slug": slug})
            _ok(respond, detail if isinstance(detail, dict) else {"slug": slug})
        except Exception as exc:
            _unavailable(respond, str(exc))
        return
    manifest = load_skill_manifest(slug)
    if manifest is None:
        for m in discover_workspace_skill_manifests():
            if m.name == slug:
                manifest = m
                break
    if manifest is None:
        _bad(respond, f"unknown skill slug: {slug}")
        return
    _ok(
        respond,
        {
            "slug": manifest.name,
            "name": manifest.name,
            "description": manifest.description,
            "skillDir": manifest.skill_dir,
            "skillFile": manifest.skill_file,
            "metadata": {"oclaw": dict(manifest.metadata_oclaw)},
            "body": manifest.body,
        },
    )


def _skills_install_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    store = _get_store(context)
    if store is None:
        _unavailable(respond, "skills.install requires context.store")
        return
    if not isinstance(params, dict):
        _bad(respond, "invalid skills.install params")
        return
    source = _normalize_optional_str(params.get("source")) or "local"
    if source == "clawhub":
        hook = context.get("install_skill_from_clawhub") if isinstance(context, dict) else None
        if not callable(hook):
            _unavailable(respond, "clawhub install is not configured")
            return
        try:
            result = hook(dict(params))
            _ok(respond, result)
        except Exception as exc:
            _unavailable(respond, str(exc))
        return

    overwrite = bool(params.get("force"))
    archive_url = _normalize_optional_str(params.get("archiveUrl"))
    source_dir = _normalize_optional_str(params.get("sourceDir"))
    if archive_url:
        res = install_skill_from_registry_archive(store=store, archive_url=archive_url, overwrite=overwrite)
        _ok(respond, {"ok": res.ok, "result": res.__dict__})
        return
    if source_dir:
        res = install_skill_from_local_dir(store=store, source_dir=source_dir, overwrite=overwrite)
        _ok(respond, {"ok": res.ok, "result": res.__dict__})
        return

    name = _normalize_optional_str(params.get("name"))
    if not name:
        _bad(respond, "invalid skills.install params: name required (or archiveUrl/sourceDir)")
        return
    description = _normalize_optional_str(params.get("description")) or f"{name} skill"
    body = _normalize_optional_str(params.get("body")) or ""
    md = params.get("metadata_oclaw")
    md = dict(md) if isinstance(md, dict) else {}
    res = create_skill_from_template(
        store=store,
        name=name,
        description=description,
        body_markdown=body,
        metadata_oclaw=md,
        overwrite=overwrite,
    )
    _ok(respond, {"ok": res.ok, "result": res.__dict__})


def _skills_update_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    store = _get_store(context)
    if store is None:
        _unavailable(respond, "skills.update requires context.store")
        return
    if not isinstance(params, dict):
        _bad(respond, "invalid skills.update params")
        return
    source = _normalize_optional_str(params.get("source"))
    if source == "clawhub":
        hook = context.get("update_skills_from_clawhub") if isinstance(context, dict) else None
        if not callable(hook):
            _unavailable(respond, "clawhub update is not configured")
            return
        slug = _normalize_optional_str(params.get("slug"))
        all_flag = bool(params.get("all"))
        if not slug and not all_flag:
            _bad(respond, 'clawhub skills.update requires "slug" or "all"')
            return
        if slug and all_flag:
            _bad(respond, 'clawhub skills.update accepts either "slug" or "all", not both')
            return
        try:
            result = hook(dict(params))
            _ok(respond, result)
        except Exception as exc:
            _unavailable(respond, str(exc))
        return

    skill_key = _normalize_optional_str(params.get("skillKey"))
    if not skill_key:
        _bad(respond, "invalid skills.update params: skillKey required")
        return
    if isinstance(params.get("enabled"), bool):
        set_skill_enabled(store=store, skill_name=skill_key, enabled=bool(params["enabled"]))

    api_key = params.get("apiKey")
    if isinstance(api_key, str):
        trimmed = api_key.strip()
        store.set_setting(f"SKILL_API_KEY:{skill_key}", trimmed)
    env = params.get("env")
    if isinstance(env, dict):
        clean: dict[str, str] = {}
        for k, v in env.items():
            kk = _normalize_optional_str(k)
            vv = _normalize_optional_str(v)
            if not kk:
                continue
            if vv is None:
                continue
            clean[kk] = vv
        store.set_setting(f"SKILL_ENV:{skill_key}", json.dumps(clean, ensure_ascii=False))

    _ok(respond, {"ok": True, "skillKey": skill_key})


skills_handlers: GatewayRequestHandlers = {
    "skills.status": _skills_status_handler,
    "skills.bins": _skills_bins_handler,
    "skills.search": _skills_search_handler,
    "skills.detail": _skills_detail_handler,
    "skills.install": _skills_install_handler,
    "skills.update": _skills_update_handler,
}
