from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


# ── Language extension map ────────────────────────────────────────
LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript React",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".go": "Go",
    ".java": "Java",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".sql": "SQL",
    ".env": "Environment Variables",
    ".ini": "INI Config",
    ".cfg": "Config",
    ".txt": "Text",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".hs": "Haskell",
    ".zig": "Zig",
    ".nim": "Nim",
    ".pl": "Perl",
    ".pm": "Perl Module",
    ".tcl": "Tcl",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
}

# ── Entry point patterns ──────────────────────────────────────────
ENTRY_PATTERNS = frozenset({
    "main.py", "app.py", "index.py", "cli.py", "manage.py",
    "wsgi.py", "asgi.py", "run.py", "server.py",
    "index.js", "index.ts", "app.js", "app.ts", "server.js", "server.ts",
    "main.go", "main.rs", "main.java", "Main.java",
    "main.kt", "main.scala",
})

# ── Test framework indicators ─────────────────────────────────────
TEST_FILES: dict[str, list[str]] = {
    "pytest": ["pytest.ini", "conftest.py", "pyproject.toml"],
    "jest": ["jest.config.js", "jest.config.ts", "jest.config.json", "jest.config.mjs"],
    "vitest": ["vitest.config.ts", "vitest.config.js"],
    "mocha": [".mocharc.yml", ".mocharc.js", ".mocharc.json"],
    "playwright": ["playwright.config.ts", "playwright.config.js"],
    "cypress": ["cypress.config.ts", "cypress.config.js"],
    "rspec": [".rspec"],
}

# ── Package manager indicators ────────────────────────────────────
PKG_FILES: dict[str, list[str]] = {
    "pip": ["requirements.txt", "setup.py", "setup.cfg"],
    "poetry": ["pyproject.toml"],
    "uv": ["uv.lock"],
    "npm": ["package.json", "package-lock.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "bun": ["bun.lockb"],
    "cargo": ["Cargo.toml", "Cargo.lock"],
    "go_modules": ["go.mod", "go.sum"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "composer": ["composer.json", "composer.lock"],
    "gem": ["Gemfile", "Gemfile.lock"],
    "swiftpm": ["Package.swift"],
    "mix": ["mix.exs"],
}

# Directories to skip during scanning
SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".eggs", "eggs", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".hypothesis", ".coverage", "htmlcov",
    "dist", "build", ".next", ".nuxt", ".output",
    "target", "vendor", ".bundle", ".gradle", ".idea", ".vscode",
    ".svn", ".hg", ".DS_Store",
})

# Hidden dirs we still descend into (CI, hooks, local toolchain metadata)
KEEP_DOT_DIRS = frozenset({
    ".github", ".husky", ".cargo", ".gitea", ".gitlab", ".buildkite", ".woodpecker",
})

# Hard cap so callers cannot request an unbounded walk
_MAX_FILES_CAP = 50_000


def _walkable_dir(name: str) -> bool:
    if name in SKIP_DIRS:
        return False
    if name.startswith(".") and name not in KEEP_DOT_DIRS:
        return False
    return True


def _scan_workspace(root: Path, max_files: int = 5000) -> tuple[list[dict[str, Any]], int]:
    """Scan workspace files, returning (file_infos, skipped_dir_entries)."""
    files: list[dict[str, Any]] = []
    skipped_dirs_count = 0

    try:
        for dirpath_str, dirnames, filenames in os.walk(root, followlinks=False):
            if len(files) >= max_files:
                dirnames[:] = []
                continue

            dirpath = Path(dirpath_str)
            before = list(dirnames)
            dirnames[:] = [d for d in dirnames if _walkable_dir(d)]
            skipped_dirs_count += len(before) - len(dirnames)

            rel = dirpath.relative_to(root) if dirpath != root else Path(".")

            for fname in filenames:
                if len(files) >= max_files:
                    break
                if fname.startswith(".") and fname not in (
                    ".env", ".gitignore", ".dockerignore", ".editorconfig", ".prettierrc",
                ):
                    continue

                try:
                    fp = dirpath / fname
                    st = fp.stat()
                except OSError:
                    continue

                suffix = fp.suffix.lower()
                ext = suffix or (fname if "." not in fname else "")

                if st.st_size == 0 and suffix not in (".env", ".gitignore"):
                    continue

                files.append({
                    "path": str(rel / fname) if str(rel) != "." else fname,
                    "size": st.st_size,
                    "ext": ext,
                    "suffix": suffix,
                })

            if len(files) >= max_files:
                dirnames[:] = []
    except PermissionError:
        pass

    return files, skipped_dirs_count


def _build_language_stats(
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build language breakdown from scanned files."""
    ext_counter: dict[str, int] = {}
    ext_bytes: dict[str, int] = {}
    lang_files: dict[str, int] = {}
    lang_bytes: dict[str, int] = {}

    for f in files:
        ext = f["ext"]
        ext_counter[ext] = ext_counter.get(ext, 0) + 1
        ext_bytes[ext] = ext_bytes.get(ext, 0) + f["size"]

    for ext, count in ext_counter.items():
        lang = LANGUAGE_MAP.get(ext, ext.lstrip(".").capitalize() if ext else "Other")
        lang_files[lang] = lang_files.get(lang, 0) + count
        lang_bytes[lang] = lang_bytes.get(lang, 0) + ext_bytes.get(ext, 0)

    total_files = sum(lang_files.values())
    total_bytes = sum(lang_bytes.values())

    sorted_langs = sorted(lang_files.items(), key=lambda x: -x[1])

    breakdown = []
    for lang, count in sorted_langs:
        b = lang_bytes[lang]
        breakdown.append({
            "language": lang,
            "files": count,
            "bytes": b,
            "pct": round(count / total_files * 100, 1) if total_files else 0,
        })

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "languages": breakdown,
        "top_language": breakdown[0]["language"] if breakdown else None,
    }


def _find_largest_files(
    files: list[dict[str, Any]], top_n: int = 10,
) -> list[dict[str, Any]]:
    """Find the largest files by byte size."""
    sorted_files = sorted(files, key=lambda x: -x["size"])
    result = []
    for f in sorted_files[:top_n]:
        result.append({
            "path": f["path"],
            "bytes": f["size"],
            "ext": f["suffix"] or f["ext"],
        })
    return result


def _looks_like_test_file(rel: str) -> bool:
    pp = Path(rel)
    name = pp.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    parts = pp.parts
    if "tests" in parts:
        return True
    return any(part.startswith("test_") for part in parts)


def _detect_test_framework(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect test frameworks used in the project."""
    detected: list[str] = []
    configs: list[str] = []
    test_file_count = 0

    file_names = {Path(f["path"]).name for f in files}

    for framework, indicators in TEST_FILES.items():
        for ind in indicators:
            if ind in file_names:
                detected.append(framework)
                configs.append(ind)
                break

    for f in files:
        if _looks_like_test_file(f["path"]):
            test_file_count += 1

    return {
        "detected": len(detected) > 0 or test_file_count > 0,
        "frameworks": detected if detected else (["unittest"] if test_file_count > 0 else []),
        "config_files": configs,
        "test_file_count": test_file_count,
    }


def _detect_package_manager(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect package managers used in the project."""
    detected: list[str] = []
    configs: list[str] = []
    file_names = {Path(f["path"]).name for f in files}

    for manager, indicators in PKG_FILES.items():
        for ind in indicators:
            if ind in file_names:
                detected.append(manager)
                configs.append(ind)
                break

    if any(Path(f["path"]).suffix.lower() == ".csproj" for f in files):
        detected.append("nuget")
        first = next((f["path"] for f in files if Path(f["path"]).suffix.lower() == ".csproj"), "")
        if first:
            configs.append(Path(first).name)

    return {
        "detected": len(detected) > 0,
        "managers": detected,
        "config_files": configs,
    }


def _find_entry_points(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find common project entry points."""
    entries: list[dict[str, Any]] = []
    file_names = {Path(f["path"]).name for f in files}

    for pattern in ENTRY_PATTERNS:
        if pattern in file_names:
            entries.append({
                "path": pattern,
                "type": _classify_entry(pattern),
            })

    for f in files:
        parts = Path(f["path"]).parts
        if len(parts) >= 2 and parts[0] in ("cmd", "bin"):
            name = Path(f["path"]).name
            if name not in {e["path"] for e in entries}:
                entries.append({
                    "path": f["path"],
                    "type": "cli_entry",
                })

    return entries


def _classify_entry(name: str) -> str:
    if name.endswith(".py"):
        return "python_entry"
    elif name.endswith((".js", ".mjs", ".cjs")):
        return "js_entry"
    elif name.endswith((".ts", ".mts", ".cts")):
        return "ts_entry"
    elif name.endswith(".go"):
        return "go_entry"
    elif name.endswith(".rs"):
        return "rust_entry"
    elif name.endswith((".java", ".kt", ".scala")):
        return "jvm_entry"
    return "unknown"


def _get_git_status(root: Path) -> dict[str, Any]:
    """Get git status summary."""
    git_root = root / ".git"
    if not git_root.exists():
        return {"detected": False}

    result: dict[str, Any] = {"detected": True}

    try:
        # Branch
        branch_proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        result["branch"] = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "unknown"

        # Status - porcelain
        status_proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in status_proc.stdout.strip().split("\n") if l.strip()]
        modified = sum(1 for l in lines if l.startswith(" M") or l.startswith("M ") or l.startswith("MM"))
        added = sum(1 for l in lines if l.startswith("A "))
        deleted = sum(1 for l in lines if l.startswith(" D") or l.startswith("D "))
        renamed = sum(1 for l in lines if l.startswith("R "))
        untracked = sum(1 for l in lines if l.startswith("??"))

        result["modified"] = modified
        result["added"] = added
        result["deleted"] = deleted
        result["renamed"] = renamed
        result["untracked"] = untracked
        result["total_uncommitted"] = len(lines)

        # Recent commits
        log_proc = subprocess.run(
            ["git", "-C", str(root), "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=5,
        )
        if log_proc.returncode == 0:
            recent = [l.strip() for l in log_proc.stdout.strip().split("\n") if l.strip()]
            result["recent_commits"] = recent

        # Last commit
        last_proc = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%h %s (%ai)"],
            capture_output=True, text=True, timeout=5,
        )
        if last_proc.returncode == 0:
            result["last_commit"] = last_proc.stdout.strip()

    except Exception as exc:
        result["error"] = str(exc)

    return result


def _path_suggests_ci(rel: str) -> bool:
    p = rel.replace("\\", "/")
    pl = p.lower()
    if ".github/workflows/" in pl:
        return True
    name = Path(p).name.lower()
    if name in (
        "jenkinsfile",
        ".gitlab-ci.yml",
        "gitlab-ci.yml",
        "azure-pipelines.yml",
        ".travis.yml",
        "appveyor.yml",
        "buildkite.yml",
        "bitbucket-pipelines.yml",
    ):
        return True
    parts = tuple(Path(pl).parts)
    if ".circleci" in parts or ".woodpecker" in parts:
        return True
    return any(seg == "jenkinsfile" for seg in parts)


def _generate_suggestions(
    lang_stats: dict[str, Any],
    test: dict[str, Any],
    pkg: dict[str, Any],
    entries: list[dict[str, Any]],
    git: dict[str, Any],
    file_count: int,
    files: list[dict[str, Any]],
) -> list[str]:
    """Generate actionable suggestions based on profile."""
    suggestions: list[str] = []

    top_lang = lang_stats.get("top_language")

    # Missing test framework
    if not test.get("detected"):
        suggestions.append("未检测到测试框架。建议引入 pytest 并为关键模块编写测试。")

    # Missing package manager
    if not pkg.get("detected"):
        if top_lang == "Python":
            suggestions.append("未检测到包管理器配置文件。建议添加 pyproject.toml 或 requirements.txt。")
        elif top_lang in ("JavaScript", "TypeScript"):
            suggestions.append("未检测到包管理器。建议初始化 package.json（npm init）。")
        elif top_lang == "Go":
            suggestions.append("未检测到 Go module。建议运行 go mod init <module-name>。")

    # Many uncommitted changes
    uncommitted = git.get("total_uncommitted", 0)
    if git.get("detected") and uncommitted > 10:
        suggestions.append(f"有 {uncommitted} 个未提交的变更。建议分批次提交以保持历史清晰。")

    # No entry points found
    if not entries:
        suggestions.append("未检测到常见入口文件。项目结构可能需要明确的主入口。")

    if file_count > 200:
        has_ci = any(_path_suggests_ci(f["path"]) for f in files)
        if not has_ci:
            suggestions.append(
                "文件量较多但未发现常见 CI 配置（如 .github/workflows、Jenkinsfile、"
                ".gitlab-ci.yml、Azure Pipelines、CircleCI、Bitbucket Pipelines）。可考虑补充自动化流水线。"
            )

    return suggestions


def workspace_profile_tool() -> ToolSpec:
    """Workspace profile — one-shot codebase overview."""

    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        root_raw = str(args.get("root") or ".").strip()
        max_files = int(args.get("max_files") or 5000)
        if max_files <= 0:
            max_files = 1
        if max_files > _MAX_FILES_CAP:
            max_files = _MAX_FILES_CAP

        try:
            root = resolve_workspace_path(root_raw)
        except Exception as exc:
            return {"ok": False, "error_code": "invalid_root", "detail": str(exc)}

        if not root.is_dir():
            return {"ok": False, "error_code": "not_a_directory", "detail": str(root)}

        # ── Scan ──────────────────────────────────────────────────
        files, skipped = _scan_workspace(root, max_files=max_files)

        # ── Profile sections ──────────────────────────────────────
        lang_stats = _build_language_stats(files)
        largest = _find_largest_files(files, top_n=10)
        test_info = _detect_test_framework(files)
        pkg_info = _detect_package_manager(files)
        entries = _find_entry_points(files)
        git_info = _get_git_status(root)
        suggestions = _generate_suggestions(
            lang_stats, test_info, pkg_info, entries, git_info, len(files), files,
        )

        # ── Assemble ──────────────────────────────────────────────
        profile = {
            "project_name": root.name,
            "total_files_scanned": len(files),
            "skipped_dirs": skipped,
            "truncated": len(files) >= max_files,
            "languages": lang_stats,
            "largest_files": largest,
            "test_framework": test_info,
            "package_manager": pkg_info,
            "entry_points": entries,
            "git": git_info,
            "suggestions": suggestions,
        }

        return {"ok": True, "profile": profile}

    return ToolSpec(
        name="workspace_profile",
        description=(
            "Quick codebase profiling: language breakdown, largest files, test framework, package manager, "
            "entry points, git status, and actionable suggestions. Filesystem walk with common vendor/build "
            "directories skipped; not .gitignore-aware (unlike ripgrep). One-shot overview for unfamiliar projects."
        ),
        parameters={
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "default": ".",
                    "description": "Directory to profile (relative to workspace root).",
                },
                "max_files": {
                    "type": "integer",
                    "default": 5000,
                    "description": "Maximum files to collect (1–50000; prevents hangs on large repos).",
                },
            },
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "profile", "workspace", "analysis", "readonly"}),
        risk_level="low",
        read_only=True,
        timeout_s=60.0,
    )


__all__ = ["workspace_profile_tool"]
