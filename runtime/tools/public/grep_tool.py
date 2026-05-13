from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def grep_tool() -> ToolSpec:
    """Grep / ripgrep — fast file content search with fallback."""

    # ── engine detection ──────────────────────────────────────────
    def _detect_engine() -> str:
        return "ripgrep" if shutil.which("rg") else "python"

    # ── ripgrep backend ───────────────────────────────────────────
    def _rg_search(
        pattern: str,
        root: Path,
        *,
        case_insensitive: bool = False,
        word_regexp: bool = False,
        files_with_matches: bool = False,
        count_only: bool = False,
        context_lines: int = 0,
        glob: str | None = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        # ripgrep forbids --json together with -l / -c (see rg manpage OUTPUT MODES).
        use_json = not files_with_matches and not count_only
        cmd = ["rg"]
        if use_json:
            cmd.extend(["--json", "--line-number", "--column"])
        if case_insensitive:
            cmd.append("-i")
        if word_regexp:
            cmd.append("-w")
        if files_with_matches:
            cmd.append("-l")
        if count_only:
            cmd.append("-c")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if glob:
            cmd.extend(["-g", glob])
        cmd.extend([pattern, str(root)])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error_code": "timeout", "detail": "rg search timed out after 30s"}
        except Exception as exc:
            return {"ok": False, "error_code": "rg_failed", "detail": str(exc)}

        if proc.returncode not in (0, 1):
            return {
                "ok": False,
                "error_code": "rg_error",
                "detail": (proc.stderr.strip() or f"exit_code={proc.returncode}"),
            }

        # ── files-with-matches mode ──
        if files_with_matches:
            files = [f.strip() for f in proc.stdout.strip().split("\n") if f.strip()]
            return {
                "ok": True,
                "engine": "ripgrep",
                "files_with_matches": True,
                "files": files,
                "total_files": len(files),
            }

        # ── count mode ──
        if count_only:
            counts: dict[str, int] = {}
            for line in proc.stdout.strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    fp, cnt = line.rsplit(":", 1)
                    counts[fp.strip()] = int(cnt.strip())
            return {
                "ok": True,
                "engine": "ripgrep",
                "count": True,
                "file_counts": counts,
            }

        # ── standard match mode (JSON) ──
        matches: list[dict[str, Any]] = []
        file_map: dict[str, list[int]] = {}

        for raw_line in proc.stdout.strip().split("\n"):
            if not raw_line.strip():
                continue
            if len(matches) >= max_results:
                break
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "match":
                continue
            data = obj.get("data", {})
            filepath = data.get("path", {}).get("text", "")
            line_num = data.get("line_number", 0)
            line_text = data.get("lines", {}).get("text", "").rstrip("\n").rstrip("\r")
            submatches = data.get("submatches", [])
            col = (submatches[0].get("start", 0) + 1) if submatches else 0

            match_entry: dict[str, Any] = {
                "file": filepath,
                "line": line_num,
                "column": col,
                "preview": line_text,
            }
            matches.append(match_entry)
            file_map.setdefault(filepath, []).append(len(matches) - 1)

        # ── attach context lines if requested ──
        if context_lines > 0 and matches:
            for filepath, indices in file_map.items():
                try:
                    fp = Path(filepath)
                    if not fp.is_absolute():
                        fp = root / filepath
                    f_lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                for idx in indices:
                    m = matches[idx]
                    ln = m["line"] - 1  # 0-indexed
                    start = max(0, ln - context_lines)
                    end = min(len(f_lines), ln + context_lines + 1)
                    m["before"] = [f_lines[i] for i in range(start, ln)]
                    m["after"] = [f_lines[i] for i in range(ln + 1, end)]

        total_files = len(file_map)
        return {
            "ok": True,
            "engine": "ripgrep",
            "matches": matches,
            "total_matches": len(matches),
            "files_with_matches": total_files,
        }

    # ── Python fallback backend ───────────────────────────────────
    def _py_search(
        pattern: str,
        root: Path,
        *,
        case_insensitive: bool = False,
        word_regexp: bool = False,
        files_with_matches: bool = False,
        count_only: bool = False,
        context_lines: int = 0,
        glob: str | None = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        flags = re.IGNORECASE if case_insensitive else 0
        pat_str = rf"\b{pattern}\b" if word_regexp else pattern
        try:
            matcher = re.compile(pat_str, flags)
        except re.error as exc:
            return {"ok": False, "error_code": "invalid_regex", "detail": str(exc)}

        try:
            if root.is_file():
                file_list = [root]
            else:
                file_list = sorted(root.rglob(glob or "**/*"))
                file_list = [p for p in file_list if p.is_file()]
        except Exception as exc:
            return {"ok": False, "error_code": "scan_failed", "detail": str(exc)}

        scanned = 0
        matches: list[dict[str, Any]] = []
        file_counts: dict[str, int] = {}

        for fp in file_list:
            if len(matches) >= max_results and not (files_with_matches or count_only):
                break
            scanned += 1
            try:
                lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            file_hit_count = 0
            for idx, line in enumerate(lines):
                m = matcher.search(line)
                if not m:
                    continue
                file_hit_count += 1
                try:
                    rel_path = str(fp.relative_to(root))
                except ValueError:
                    rel_path = str(fp)

                if files_with_matches:
                    if file_hit_count == 1:
                        matches.append({"file": rel_path})
                    continue

                if count_only:
                    file_counts[rel_path] = file_hit_count
                    continue

                col = m.start() + 1
                match_entry: dict[str, Any] = {
                    "file": rel_path,
                    "line": idx + 1,
                    "column": col,
                    "preview": line,
                }
                if context_lines > 0:
                    start = max(0, idx - context_lines)
                    end = min(len(lines), idx + context_lines + 1)
                    match_entry["before"] = [lines[i] for i in range(start, idx)]
                    match_entry["after"] = [lines[i] for i in range(idx + 1, end)]
                matches.append(match_entry)

                if len(matches) >= max_results:
                    break

        if files_with_matches:
            files = sorted(set(m["file"] for m in matches))
            return {
                "ok": True,
                "engine": "python",
                "files_with_matches": True,
                "files": files,
                "total_files": len(files),
            }

        if count_only:
            return {
                "ok": True,
                "engine": "python",
                "count": True,
                "file_counts": file_counts,
            }

        return {
            "ok": True,
            "engine": "python",
            "matches": matches,
            "total_matches": len(matches),
            "files_with_matches": len(set(m.get("file") for m in matches)),
            "scanned_files": scanned,
        }

    # ── main handler ──────────────────────────────────────────────
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "").strip()
        root_raw = str(args.get("root") or ".").strip()
        glob_pat = str(args.get("glob") or "").strip() or None
        case_insensitive = bool(args.get("case_insensitive", False))
        word_regexp = bool(args.get("word_regexp", False))
        files_with_matches = bool(args.get("files_with_matches", False))
        count_only = bool(args.get("count", False))
        context_lines = int(args.get("context_lines") or 0)
        max_results = int(args.get("max_results") or 200)

        if not pattern:
            return {"ok": False, "error_code": "pattern_required", "detail": "pattern is required"}
        if max_results <= 0:
            max_results = 1
        if context_lines < 0:
            context_lines = 0

        try:
            root = resolve_workspace_path(root_raw)
        except Exception as exc:
            return {"ok": False, "error_code": "invalid_root", "detail": str(exc)}

        engine = _detect_engine()

        if engine == "ripgrep":
            result = _rg_search(
                pattern, root,
                case_insensitive=case_insensitive,
                word_regexp=word_regexp,
                files_with_matches=files_with_matches,
                count_only=count_only,
                context_lines=context_lines,
                glob=glob_pat,
                max_results=max_results,
            )
            if result.get("ok"):
                return result
            rg_error = result.get("detail", "")
        else:
            rg_error = ""

        py_result = _py_search(
            pattern, root,
            case_insensitive=case_insensitive,
            word_regexp=word_regexp,
            files_with_matches=files_with_matches,
            count_only=count_only,
            context_lines=context_lines,
            glob=glob_pat,
            max_results=max_results,
        )
        if not py_result.get("ok"):
            return py_result

        if rg_error and engine == "ripgrep":
            py_result["_rg_fallback_reason"] = rg_error
        return py_result

    # ── ToolSpec ──────────────────────────────────────────────────
    return ToolSpec(
        name="grep",
        description="Fast file content search (grep). Uses ripgrep (`rg`) if available, falls back to Python regex. Supports regex, case-insensitive, word-regexp, files-with-matches, count, and context lines. Automatically respects .gitignore when using ripgrep.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex).",
                },
                "root": {
                    "type": "string",
                    "default": ".",
                    "description": "Directory to search under.",
                },
                "glob": {
                    "type": "string",
                    "default": "",
                    "description": "Only search files matching glob, e.g. '*.py' or '*.{py,js}'. When omitted, all files are searched.",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Case-insensitive search.",
                },
                "word_regexp": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only match whole words (wraps pattern in \\b...\\b).",
                },
                "files_with_matches": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only list filenames that contain matches (like `rg -l`).",
                },
                "count": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only return match count per file (like `rg -c`).",
                },
                "context_lines": {
                    "type": "integer",
                    "default": 0,
                    "description": "Number of context lines before and after each match.",
                },
                "max_results": {
                    "type": "integer",
                    "default": 200,
                    "description": "Maximum number of matches to return.",
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "search", "workspace", "grep"}),
        risk_level="low",
        read_only=True,
        timeout_s=35.0,
    )


__all__ = ["grep_tool"]
