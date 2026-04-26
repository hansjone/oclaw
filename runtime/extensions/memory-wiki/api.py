from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_plugin_config_schema(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "wiki_root": {
                "type": "string",
                "description": "Wiki root directory relative to workspace root.",
                "default": "docs/memory-system/wiki",
            },
            "max_search_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 20,
            },
            "max_get_lines": {
                "type": "integer",
                "minimum": 20,
                "maximum": 5000,
                "default": 800,
            },
        },
        "additionalProperties": True,
    }


@dataclass(frozen=True)
class WikiRuntime:
    wiki_root: Path
    max_search_results: int
    max_get_lines: int


def _resolve_runtime(api: Any) -> WikiRuntime:
    cfg = dict(getattr(api, "plugin_config", {}) or {})
    root_cfg = str(cfg.get("wiki_root") or "docs/memory-system/wiki").strip()
    if not root_cfg:
        root_cfg = "docs/memory-system/wiki"
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (_project_root() / root).resolve()
    max_search_results = int(cfg.get("max_search_results") or 20)
    max_get_lines = int(cfg.get("max_get_lines") or 800)
    max_search_results = max(1, min(max_search_results, 200))
    max_get_lines = max(20, min(max_get_lines, 5000))
    return WikiRuntime(wiki_root=root, max_search_results=max_search_results, max_get_lines=max_get_lines)


def _safe_path(rt: WikiRuntime, rel_path: str) -> Path:
    rp = str(rel_path or "").strip().replace("\\", "/")
    rp = rp.lstrip("./")
    if not rp:
        raise ValueError("path_required")
    p = (rt.wiki_root / rp).resolve()
    root = rt.wiki_root.resolve()
    if p != root and root not in p.parents:
        raise ValueError("path_outside_wiki_root")
    if p.suffix.lower() != ".md":
        raise ValueError("only_markdown_supported")
    return p


def _list_md_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*.md") if p.is_file()])


def _read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return text.splitlines()


def _wiki_status(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    del args
    files = _list_md_files(rt.wiki_root)
    return {
        "ok": True,
        "wiki_root": str(rt.wiki_root),
        "exists": bool(rt.wiki_root.exists()),
        "file_count": len(files),
        "max_search_results": rt.max_search_results,
        "max_get_lines": rt.max_get_lines,
    }


def _wiki_get(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    path = _safe_path(rt, str(args.get("path") or ""))
    if not path.exists():
        return {"ok": False, "error_code": "wiki_not_found", "error": f"file not found: {path}"}
    start = int(args.get("start_line") or 1)
    end = int(args.get("end_line") or 0)
    lines = _read_lines(path)
    n = len(lines)
    start = max(1, min(start, n if n > 0 else 1))
    if end <= 0:
        end = min(n, start + rt.max_get_lines - 1)
    end = max(start, min(end, n))
    out_lines = lines[start - 1 : end]
    return {
        "ok": True,
        "path": str(path.relative_to(rt.wiki_root)),
        "start_line": start,
        "end_line": end,
        "content": "\n".join(out_lines),
    }


def _wiki_search(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error_code": "query_required", "error": "query is required"}
    case_sensitive = bool(args.get("case_sensitive"))
    is_regex = bool(args.get("is_regex"))
    req_limit = int(args.get("limit") or rt.max_search_results)
    limit = max(1, min(req_limit, rt.max_search_results))
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(query if is_regex else re.escape(query), flags=flags)
    hits: list[dict[str, Any]] = []
    for fp in _list_md_files(rt.wiki_root):
        rel = str(fp.relative_to(rt.wiki_root)).replace("\\", "/")
        for idx, line in enumerate(_read_lines(fp), start=1):
            if pattern.search(line):
                hits.append({"path": rel, "line": idx, "text": line.strip()})
                if len(hits) >= limit:
                    return {"ok": True, "query": query, "hits": hits, "truncated": True}
    return {"ok": True, "query": query, "hits": hits, "truncated": False}


def _wiki_lint(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("path") or "").strip()
    files = [_safe_path(rt, target)] if target else _list_md_files(rt.wiki_root)
    issues: list[dict[str, Any]] = []
    for fp in files:
        if not fp.exists():
            issues.append({"path": str(fp), "line": 1, "level": "error", "code": "wiki_not_found"})
            continue
        rel = str(fp.relative_to(rt.wiki_root)).replace("\\", "/")
        lines = _read_lines(fp)
        h1_count = 0
        prev_level = 0
        for idx, line in enumerate(lines, start=1):
            m = re.match(r"^\s*(#{1,6})\s+\S+", line)
            if m:
                level = len(m.group(1))
                if level == 1:
                    h1_count += 1
                if prev_level > 0 and level > prev_level + 1:
                    issues.append(
                        {
                            "path": rel,
                            "line": idx,
                            "level": "warn",
                            "code": "heading_jump",
                            "message": f"heading jump h{prev_level} -> h{level}",
                        }
                    )
                prev_level = level
            if line.rstrip(" \t") != line:
                issues.append({"path": rel, "line": idx, "level": "warn", "code": "trailing_whitespace"})
        if h1_count > 1:
            issues.append({"path": rel, "line": 1, "level": "warn", "code": "multiple_h1", "count": h1_count})
    errors = [x for x in issues if str(x.get("level")) == "error"]
    return {"ok": len(errors) == 0, "issue_count": len(issues), "issues": issues}


def _wiki_apply(rt: WikiRuntime, args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "write").strip().lower()
    path = _safe_path(rt, str(args.get("path") or ""))
    content = str(args.get("content") or "")
    path.parent.mkdir(parents=True, exist_ok=True)
    if action == "delete":
        if not path.exists():
            return {"ok": False, "error_code": "wiki_not_found", "error": f"file not found: {path}"}
        path.unlink()
        return {"ok": True, "action": "delete", "path": str(path.relative_to(rt.wiki_root))}
    if action == "append":
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        sep = "" if not old or old.endswith("\n") else "\n"
        path.write_text(old + sep + content, encoding="utf-8")
        return {"ok": True, "action": "append", "path": str(path.relative_to(rt.wiki_root))}
    if action == "write":
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "action": "write", "path": str(path.relative_to(rt.wiki_root))}
    return {"ok": False, "error_code": "invalid_action", "error": f"unsupported action: {action}"}


def build_wiki_tool_specs(api: Any) -> list[dict[str, Any]]:
    rt = _resolve_runtime(api)

    def _wrap(fn: Callable[[WikiRuntime, dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def _handler(args: dict[str, Any]) -> dict[str, Any]:
            try:
                return fn(rt, dict(args or {}))
            except ValueError as exc:
                return {"ok": False, "error_code": "invalid_arguments", "error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error_code": "wiki_runtime_error", "error": f"{type(exc).__name__}: {exc}"}

        return _handler

    base_obj = {"type": "object", "additionalProperties": False}
    return [
        {
            "name": "wiki_status",
            "description": "Show wiki plugin status and basic file counts.",
            "parameters": {**base_obj, "properties": {}},
            "handler": _wrap(_wiki_status),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_get",
            "description": "Read a markdown file from wiki root with optional line range.",
            "parameters": {
                **base_obj,
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
            "handler": _wrap(_wiki_get),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_search",
            "description": "Search markdown files under wiki root.",
            "parameters": {
                **base_obj,
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "is_regex": {"type": "boolean"},
                    "case_sensitive": {"type": "boolean"},
                },
                "required": ["query"],
            },
            "handler": _wrap(_wiki_search),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_lint",
            "description": "Lint wiki markdown files (headings and formatting checks).",
            "parameters": {
                **base_obj,
                "properties": {"path": {"type": "string"}},
            },
            "handler": _wrap(_wiki_lint),
            "tags": ["memory", "wiki", "read"],
            "read_only": True,
        },
        {
            "name": "wiki_apply",
            "description": "Apply write/append/delete on a wiki markdown file.",
            "parameters": {
                **base_obj,
                "properties": {
                    "action": {"type": "string", "enum": ["write", "append", "delete"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["action", "path"],
            },
            "handler": _wrap(_wiki_apply),
            "tags": ["memory", "wiki", "write"],
            "read_only": False,
            "risk_level": "high",
        },
    ]
