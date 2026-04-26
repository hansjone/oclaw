from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oclaw.runtime.skills_market import get_market_adapter
from oclaw.runtime.skills import (
    default_skills_root,
    discover_workspace_skill_manifests,
    load_skill_manifest,
)

_DISABLED_SKILLS_KEY = "AIA_SKILL_DISABLED_NAMES"
_AUTO_INSTALL_KEY = "AIA_SKILL_AUTO_INSTALL_ENABLED"


@dataclass(frozen=True)
class SkillInstallResult:
    ok: bool
    name: str
    target_dir: str
    detail: str = ""
    error_code: str = ""
    retryable: bool = False


def _classify_install_detail(detail: str) -> tuple[str, bool]:
    d = str(detail or "").strip().lower()
    if not d:
        return ("unknown", False)
    if d.startswith("download_failed") or d.startswith("extract_failed"):
        return ("transport_or_extract_error", True)
    if d in {"archive_too_large", "empty_archive", "unsupported_archive_type", "archive_url_required", "unsupported_url_scheme"}:
        return ("invalid_archive", False)
    if d in {"already_exists"}:
        return ("already_exists", False)
    if d.startswith("unsafe_") or d.startswith("skill_md_missing") or d.startswith("manifest_parse_failed"):
        return ("invalid_skill_package", False)
    if d.startswith("rollback_after_error"):
        return ("runtime_error", True)
    if d in {"installed", "created", "removed"}:
        return ("ok", False)
    return ("unknown", False)


def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}


def skill_auto_install_enabled(store: Any) -> bool:
    try:
        raw = str(store.get_setting(_AUTO_INSTALL_KEY) or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return True
    return _truthy(raw)


def _get_disabled_names(store: Any) -> set[str]:
    try:
        raw = str(store.get_setting(_DISABLED_SKILLS_KEY) or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return set()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return {str(x).strip() for x in arr if str(x).strip()}
    except Exception:
        pass
    return set()


def _set_disabled_names(store: Any, names: set[str]) -> None:
    vals = sorted({str(x).strip() for x in names if str(x).strip()})
    store.set_setting(_DISABLED_SKILLS_KEY, json.dumps(vals, ensure_ascii=False))


def list_skills_with_status(*, store: Any, skills_root: str | Path | None = None) -> list[dict[str, Any]]:
    disabled = _get_disabled_names(store)
    out: list[dict[str, Any]] = []
    for m in discover_workspace_skill_manifests(skills_root):
        runtime = dict(m.runtime or {}) if isinstance(m.runtime, dict) else {}
        out.append(
            {
                "name": m.name,
                "description": m.description,
                "skill_dir": m.skill_dir,
                "skill_file": m.skill_file,
                "enabled": m.name not in disabled,
                "install_specs": [dict(id=s.id, kind=s.kind, payload=s.payload) for s in m.install],
                "metadata_oclaw": dict(m.metadata_oclaw),
                "runtime": runtime,
                "executable": bool(runtime),
            }
        )
    return out


def set_skill_enabled(*, store: Any, skill_name: str, enabled: bool) -> None:
    name = str(skill_name or "").strip()
    if not name:
        return
    disabled = _get_disabled_names(store)
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    _set_disabled_names(store, disabled)


def uninstall_skill(
    *,
    store: Any,
    skill_name: str,
    skills_root: str | Path | None = None,
) -> SkillInstallResult:
    name = str(skill_name or "").strip()
    if not name:
        ec, rt = _classify_install_detail("name_required")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="name_required", error_code=ec, retryable=rt)
    root = Path(skills_root).resolve() if skills_root else default_skills_root()
    candidates = [root / name, root / "_workspace" / name]
    target = next((p for p in candidates if p.exists() and p.is_dir()), None)
    if target is None:
        ec, rt = _classify_install_detail("not_found")
        return SkillInstallResult(ok=False, name=name, target_dir="", detail="not_found", error_code=ec, retryable=rt)
    try:
        shutil.rmtree(target)
    except Exception as exc:
        ec, rt = _classify_install_detail("runtime_error")
        return SkillInstallResult(ok=False, name=name, target_dir=str(target), detail=f"remove_failed:{type(exc).__name__}", error_code=ec, retryable=rt)
    set_skill_enabled(store=store, skill_name=name, enabled=True)
    ec, rt = _classify_install_detail("removed")
    return SkillInstallResult(ok=True, name=name, target_dir=str(target), detail="removed", error_code=ec, retryable=rt)


def scan_skill_source_dir(src_dir: str | Path) -> tuple[bool, str]:
    src = Path(src_dir).resolve()
    if not src.exists() or not src.is_dir():
        return False, "source_dir_not_found"
    skill_md = src / "SKILL.md"
    if not skill_md.exists() or not skill_md.is_file():
        return False, "skill_md_missing"
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        nm = p.name.lower()
        if nm.endswith((".exe", ".dll", ".bat", ".cmd", ".ps1")):
            return False, f"unsafe_file_detected:{p.name}"
    return True, "ok"


def _safe_archive_members(paths: list[str]) -> bool:
    for p in paths:
        v = str(p or "").replace("\\", "/")
        if not v or v.startswith("/") or ".." in v.split("/"):
            return False
    return True


def _extract_archive_to_temp(archive_path: Path) -> tuple[bool, str, Path | None]:
    temp_dir = Path(tempfile.mkdtemp(prefix="skill_archive_"))
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = [str(x.filename or "") for x in zf.infolist()]
                if not _safe_archive_members(members):
                    return False, "unsafe_archive_path", None
                zf.extractall(temp_dir)
            return True, "ok", temp_dir
        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as tf:
                members = [str(x.name or "") for x in tf.getmembers()]
                if not _safe_archive_members(members):
                    return False, "unsafe_archive_path", None
                tf.extractall(temp_dir)
            return True, "ok", temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, "unsupported_archive_type", None
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, f"extract_failed:{type(exc).__name__}", None


def _resolve_registry_archive_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return raw
    host = str(parsed.netloc or "").strip().lower()
    if host not in {"clawhub.ai", "www.clawhub.ai"}:
        return raw
    segs = [s for s in str(parsed.path or "").split("/") if s]
    if not segs:
        return raw
    # Clawhub page URLs: https://clawhub.ai/<author>/<slug>
    # Resolve via clawhub client first (matches test + avoids adapter drift).
    try:
        if len(segs) >= 2:
            from oclaw.runtime.tools.skills.clawhub_client import get_skill_detail

            slug = str(segs[-1] or "").strip()
            if slug:
                detail = get_skill_detail(slug)
                archive_url = str((detail or {}).get("archiveUrl") or "").strip()
                if archive_url:
                    return archive_url
    except Exception:
        pass
    candidates: list[str] = []
    if len(segs) >= 1:
        candidates.append(segs[-1])
    if len(segs) >= 2:
        candidates.append(f"{segs[0]}/{segs[1]}")
    try:
        adapter = get_market_adapter("clawhub")
        for slug in candidates:
            archive_url, _ = adapter.resolve_archive_url(slug=slug, version=None)
            if archive_url:
                return archive_url
        return raw
    except Exception:
        return raw


def install_skill_from_local_dir(
    *,
    store: Any,
    source_dir: str | Path,
    overwrite: bool = False,
    skills_root: str | Path | None = None,
) -> SkillInstallResult:
    src = Path(source_dir).resolve()
    ok, detail = scan_skill_source_dir(src)
    if not ok:
        ec, rt = _classify_install_detail(detail)
        return SkillInstallResult(ok=False, name="", target_dir="", detail=detail, error_code=ec, retryable=rt)
    manifest = load_skill_manifest(src)
    if not manifest:
        ec, rt = _classify_install_detail("manifest_parse_failed")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="manifest_parse_failed", error_code=ec, retryable=rt)
    root = Path(skills_root).resolve() if skills_root else default_skills_root()
    root.mkdir(parents=True, exist_ok=True)
    safe_name = str(manifest.name).strip()
    target = root / safe_name
    if target.exists():
        if not overwrite:
            ec, rt = _classify_install_detail("already_exists")
            return SkillInstallResult(ok=False, name=manifest.name, target_dir=str(target), detail="already_exists", error_code=ec, retryable=rt)
        shutil.rmtree(target)
    shutil.copytree(src, target)
    set_skill_enabled(store=store, skill_name=manifest.name, enabled=True)
    ec, rt = _classify_install_detail("installed")
    return SkillInstallResult(ok=True, name=manifest.name, target_dir=str(target), detail="installed", error_code=ec, retryable=rt)


def install_skill_from_registry_archive(
    *,
    store: Any,
    archive_url: str,
    overwrite: bool = False,
    skills_root: str | Path | None = None,
) -> SkillInstallResult:
    url = str(archive_url or "").strip()
    if not url:
        ec, rt = _classify_install_detail("archive_url_required")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="archive_url_required", error_code=ec, retryable=rt)
    url = _resolve_registry_archive_url(url)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"https", "http", "file"}:
        ec, rt = _classify_install_detail("unsupported_url_scheme")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="unsupported_url_scheme", error_code=ec, retryable=rt)
    tmp_file = Path(tempfile.mkstemp(prefix="skill_pkg_", suffix=".bin")[1])
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Oclaw-SkillInstaller/1.0 (+https://clawhub.ai)",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if not data:
            ec, rt = _classify_install_detail("empty_archive")
            return SkillInstallResult(ok=False, name="", target_dir="", detail="empty_archive", error_code=ec, retryable=rt)
        if len(data) > 50 * 1024 * 1024:
            ec, rt = _classify_install_detail("archive_too_large")
            return SkillInstallResult(ok=False, name="", target_dir="", detail="archive_too_large", error_code=ec, retryable=rt)
        tmp_file.write_bytes(data)
        ok, detail, extracted = _extract_archive_to_temp(tmp_file)
        if not ok or extracted is None:
            ec, rt = _classify_install_detail(detail)
            return SkillInstallResult(ok=False, name="", target_dir="", detail=detail, error_code=ec, retryable=rt)
        candidates: list[Path] = []
        if (extracted / "SKILL.md").exists():
            candidates.append(extracted)
        for p in extracted.rglob("SKILL.md"):
            if p.is_file():
                candidates.append(p.parent)
        if not candidates:
            ec, rt = _classify_install_detail("skill_md_missing")
            return SkillInstallResult(ok=False, name="", target_dir="", detail="skill_md_missing", error_code=ec, retryable=rt)
        chosen = sorted(candidates, key=lambda x: len(x.parts))[0]
        return install_skill_from_local_dir(store=store, source_dir=chosen, overwrite=overwrite, skills_root=skills_root)
    except Exception as exc:
        detail = f"download_failed:{type(exc).__name__}"
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            detail = f"download_failed:http_{code}"
        ec, rt = _classify_install_detail(detail)
        return SkillInstallResult(ok=False, name="", target_dir="", detail=detail, error_code=ec, retryable=rt)
    finally:
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except Exception:
            pass
        try:
            if "extracted" in locals() and isinstance(extracted, Path) and extracted.exists():
                shutil.rmtree(extracted, ignore_errors=True)
        except Exception:
            pass


def create_skill_from_template(
    *,
    store: Any,
    name: str,
    description: str,
    body_markdown: str = "",
    metadata_oclaw: dict[str, Any] | None = None,
    skills_root: str | Path | None = None,
    overwrite: bool = False,
) -> SkillInstallResult:
    nm = str(name or "").strip()
    if not nm:
        ec, rt = _classify_install_detail("name_required")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="name_required", error_code=ec, retryable=rt)
    root = Path(skills_root).resolve() if skills_root else default_skills_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / nm
    if target.exists() and not overwrite:
        ec, rt = _classify_install_detail("already_exists")
        return SkillInstallResult(ok=False, name=nm, target_dir=str(target), detail="already_exists", error_code=ec, retryable=rt)
    target.mkdir(parents=True, exist_ok=True)
    oc = dict(metadata_oclaw or {})
    front = {
        "name": nm,
        "description": str(description or f"{nm} skill"),
        "user-invocable": "true",
        "disable-model-invocation": "false",
        "metadata": {"oclaw": oc},
    }
    text = (
        "---\n"
        f"name: {front['name']}\n"
        f"description: {front['description']}\n"
        f"user-invocable: {front['user-invocable']}\n"
        f"disable-model-invocation: {front['disable-model-invocation']}\n"
        f"metadata: {json.dumps(front['metadata'], ensure_ascii=False)}\n"
        "---\n\n"
        f"{str(body_markdown or '').strip()}\n"
    )
    (target / "SKILL.md").write_text(text, encoding="utf-8")
    set_skill_enabled(store=store, skill_name=nm, enabled=True)
    ec, rt = _classify_install_detail("created")
    return SkillInstallResult(ok=True, name=nm, target_dir=str(target), detail="created", error_code=ec, retryable=rt)


def create_workspace_skill(
    *,
    store: Any,
    name: str,
    description: str,
    runtime_type: str = "python",
    skills_root: str | Path | None = None,
    overwrite: bool = False,
) -> SkillInstallResult:
    nm = str(name or "").strip()
    if not nm:
        ec, rt = _classify_install_detail("name_required")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="name_required", error_code=ec, retryable=rt)
    rt_type = str(runtime_type or "python").strip().lower()
    if rt_type not in {"python", "shell", "node"}:
        ec, rt = _classify_install_detail("unsupported_runtime_type")
        return SkillInstallResult(ok=False, name=nm, target_dir="", detail="unsupported_runtime_type", error_code=ec, retryable=rt)
    root = Path(skills_root).resolve() if skills_root else default_skills_root()
    target = root / "_workspace" / nm
    if target.exists() and not overwrite:
        ec, rt = _classify_install_detail("already_exists")
        return SkillInstallResult(ok=False, name=nm, target_dir=str(target), detail="already_exists", error_code=ec, retryable=rt)
    target.mkdir(parents=True, exist_ok=True)
    scripts_dir = target / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    entry = "scripts/run.py" if rt_type == "python" else ("scripts/run.sh" if rt_type == "shell" else "scripts/run.js")
    script_path = target / entry
    if rt_type == "python":
        script_path.write_text(
            "import json\nimport sys\n\n"
            "def main():\n"
            "    data = json.loads(sys.stdin.read() or '{}')\n"
            "    args = data.get('args') or {}\n"
            "    print(json.dumps({'ok': True, 'echo': args}, ensure_ascii=False))\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
    elif rt_type == "shell":
        script_path.write_text("#!/usr/bin/env bash\ncat\n", encoding="utf-8")
    else:
        script_path.write_text("const fs=require('fs'); const input=JSON.parse(fs.readFileSync(0,'utf8')||'{}'); console.log(JSON.stringify({ok:true,echo:input.args||{}}));\n", encoding="utf-8")
    metadata_oclaw = {
        "source": {"kind": "workspace", "provider": "local", "version": "workspace"},
        "runtime": {
            "type": rt_type,
            "entry": entry,
            "schema": {"type": "object", "additionalProperties": True},
            "permissions": {"fs_write": False, "net": False, "process": True},
        },
    }
    return create_skill_from_template(
        store=store,
        name=nm,
        description=description,
        body_markdown="Workspace authored skill.",
        metadata_oclaw=metadata_oclaw,
        skills_root=target.parent,
        overwrite=True,
    )


def auto_install_skill_from_payload(
    *,
    store: Any,
    payload: dict[str, Any],
    skills_root: str | Path | None = None,
) -> SkillInstallResult:
    if not skill_auto_install_enabled(store):
        ec, rt = _classify_install_detail("auto_install_disabled")
        return SkillInstallResult(ok=False, name="", target_dir="", detail="auto_install_disabled", error_code=ec, retryable=rt)
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    body = str(payload.get("body_markdown") or "").strip()
    md = payload.get("metadata_oclaw")
    md = dict(md) if isinstance(md, dict) else {}
    root = Path(skills_root).resolve() if skills_root else default_skills_root()
    target = root / name
    before_disabled = _get_disabled_names(store)
    try:
        out = create_skill_from_template(
            store=store,
            name=name,
            description=description,
            body_markdown=body,
            metadata_oclaw=md,
            skills_root=skills_root,
            overwrite=False,
        )
        if bool(payload.get("force_error_for_test")):
            raise RuntimeError("forced_error_for_test")
        if not out.ok:
            return out
        return out
    except Exception as exc:
        try:
            if target.exists() and target.is_dir():
                shutil.rmtree(target)
        except Exception:
            pass
        try:
            _set_disabled_names(store, before_disabled)
        except Exception:
            pass
        detail = f"rollback_after_error:{type(exc).__name__}"
        ec, rt = _classify_install_detail(detail)
        return SkillInstallResult(ok=False, name=name, target_dir=str(target), detail=detail, error_code=ec, retryable=rt)


__all__ = [
    "SkillInstallResult",
    "auto_install_skill_from_payload",
    "create_skill_from_template",
    "create_workspace_skill",
    "install_skill_from_local_dir",
    "install_skill_from_registry_archive",
    "list_skills_with_status",
    "set_skill_enabled",
    "skill_auto_install_enabled",
    "uninstall_skill",
]
