from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BOOT_NAME = "SESSION_BOOTSTRAP.md"
BOOT_PATH = BOOT_NAME


def _is_record(v: object) -> bool:
    return isinstance(v, dict)


def _workspace_dir(event: Any) -> Path | None:
    ctx = getattr(event, "context", None)
    if isinstance(ctx, dict):
        ws = str(ctx.get("workspaceDir") or "").strip()
        if ws:
            return Path(ws).expanduser()
    env_ws = str(os.getenv("OCLAW_WORKSPACE") or "").strip()
    if env_ws:
        return Path(env_ws).expanduser()
    return None


def _repo_root() -> Path:
    # .../runtime/skills/session-bootstrap/hooks/runtime/handler.py
    return Path(__file__).resolve().parents[5]


def _wiki_root(repo_root: Path) -> Path:
    cfg = repo_root / "oclaw.json"
    default = repo_root / "data" / "wiki"
    if not cfg.exists():
        return default
    try:
        obj = json.loads(cfg.read_text(encoding="utf-8"))
        w = (
            ((obj.get("plugins") or {}).get("entries") or {}).get("memory-wiki") or {}
            if isinstance(obj, dict)
            else {}
        )
        raw = str((w or {}).get("wiki_root") or "").strip()
        if not raw:
            return default
        p = Path(raw)
        return p if p.is_absolute() else (repo_root / p).resolve()
    except Exception:
        return default


def _safe_read(path: Path, *, max_chars: int = 1200) -> str:
    try:
        txt = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    if len(txt) <= max_chars:
        return txt
    return txt[:max_chars].rstrip() + "\n...(已截断)"


def _latest_memory_file(ws_dir: Path | None) -> Path | None:
    if ws_dir is None:
        return None
    mem = ws_dir / "memory"
    if not mem.exists():
        return None
    files = [p for p in mem.glob("*.md") if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _last_nonempty_line(text: str) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[-1][:140]


def _extract_recent_learning(learnings_text: str) -> str:
    lines = [ln.strip() for ln in str(learnings_text or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("## ["):
            return ln.replace("## ", "", 1)[:140]
    return _last_nonempty_line(learnings_text)


def _extract_recent_topic(memory_text: str) -> str:
    lines = [ln.strip() for ln in str(memory_text or "").splitlines() if ln.strip()]
    for ln in lines:
        if ln.startswith("- **User**:"):
            return ln.replace("- **User**:", "", 1).strip()[:140]
    return _last_nonempty_line(memory_text)


def _build_bootstrap_content(event: Any) -> str:
    ws_dir = _workspace_dir(event)
    repo = _repo_root()
    wiki = _wiki_root(repo)

    soul = repo / "runtime" / "skills" / "session-bootstrap" / "SOUL.md"
    ident = repo / "runtime" / "skills" / "session-bootstrap" / "IDENTITY.md"
    mem_file = _latest_memory_file(ws_dir)

    learnings = wiki / "improvement" / "learnings.md"
    errors = wiki / "improvement" / "errors.md"
    feats = wiki / "improvement" / "feature-requests.md"

    soul_txt = _safe_read(soul, max_chars=800)
    ident_txt = _safe_read(ident, max_chars=800)
    mem_txt = _safe_read(mem_file, max_chars=900) if mem_file else ""
    lrn_txt = _safe_read(learnings, max_chars=900)

    topic = _extract_recent_topic(mem_txt) or "近期项目上下文"
    learning = _extract_recent_learning(lrn_txt) or "待补充新的关键学习"
    developer = "开发者"
    welcome = f"欢迎回来，{developer}。上次我们聊了{topic}，我学到了{learning}。"

    mem_path = str(mem_file) if mem_file else "(无)"
    return (
        "# 会话唤醒摘要\n\n"
        f"{welcome}\n\n"
        "## 读取顺序（必须遵循）\n"
        "1. SOUL.md\n"
        "2. IDENTITY.md\n"
        "3. memory 最新记录\n"
        "4. Wiki 改进记录\n\n"
        "## 来源\n"
        f"- SOUL: {soul}\n"
        f"- IDENTITY: {ident}\n"
        f"- memory 最新记录: {mem_path}\n"
        f"- Wiki 学习记录: {learnings}\n"
        f"- Wiki 错误记录: {errors}\n"
        f"- Wiki 需求记录: {feats}\n\n"
        "## SOUL 快照\n"
        f"{soul_txt or '(缺失)'}\n\n"
        "## IDENTITY 快照\n"
        f"{ident_txt or '(缺失)'}\n\n"
        "## 最近会话快照\n"
        f"{mem_txt or '(缺失)'}\n\n"
        "## 最近学习快照\n"
        f"{lrn_txt or '(缺失)'}\n"
    )


def _is_bootstrap_file(v: object) -> bool:
    if not _is_record(v) or str(v.get("path")) != BOOT_PATH:  # type: ignore[union-attr]
        return False
    row = v  # type: ignore[assignment]
    return bool(row.get("virtual") is True)


def handle(event: object) -> None:
    if getattr(event, "type", None) != "agent" or getattr(event, "action", None) != "bootstrap":
        return
    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        return
    session_key = str(getattr(event, "sessionKey", "") or "")
    if ":subagent:" in session_key:
        return
    files = ctx.get("bootstrapFiles")
    if not isinstance(files, list):
        return

    content = _build_bootstrap_content(event)
    occupied = any(_is_record(f) and str(f.get("path")) == BOOT_PATH and not _is_bootstrap_file(f) for f in files)
    if occupied:
        return
    cleaned = [f for f in files if not _is_bootstrap_file(f)]
    cleaned.append({"name": BOOT_NAME, "path": BOOT_PATH, "content": content, "missing": False, "virtual": True})
    ctx["bootstrapFiles"] = cleaned
