from __future__ import annotations

from pathlib import Path


def fs_safe_workspace_lane_segment(raw: str | None) -> str:
    s = "".join(c if (c.isalnum() or c in "._-") else "_" for c in str(raw or "").strip())
    s = s.strip("._")
    return (s or "lane")[:120]


def workspace_lane_segment(*, workspace_owner_session_id: str | None, session_id: str | None) -> str:
    owner = str(workspace_owner_session_id or "").strip()
    sid = str(session_id or "").strip()
    return fs_safe_workspace_lane_segment(owner or sid)


def skill_dir_private_lane_segment(skill_dir: str | Path, *, skills_home: Path | None = None) -> str | None:
    """Return the private lane key for catalog filtering.

    Layouts:

    - ``_workspace/<role>/<skill>/`` (role sibling of ``public``) → ``<role>``
    - ``_workspace/_agent/<lane>/<skill>/`` (legacy session or older role bucket) → ``<lane>``

    Flat ``_workspace/<skill>/`` (single segment) → ``None``.
    """
    from runtime.skills import default_skills_root

    home = Path(skills_home).resolve() if skills_home else default_skills_root().resolve()
    ws = (home / "_workspace").resolve()
    p = Path(skill_dir).resolve()
    try:
        rel = p.relative_to(ws)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    head = str(parts[0]).lower()
    if head == "public":
        return None
    if head == "_agent" and len(parts) >= 2:
        return str(parts[1])
    return str(parts[0])


def resolve_auto_install_parent(
    *,
    public: bool,
    workspace_lane_role: str | None = None,
    workspace_owner_session_id: str | None = None,
    session_id: str | None = None,
    skills_home: Path | None = None,
) -> Path:
    """Directory that directly contains the skill folder (sibling of ``<name>/SKILL.md``).

    - ``public``: ``_workspace/public/``
    - role installs: ``_workspace/<role>/`` (same level as ``public``, e.g. ``generalist``, ``ops``)
    - legacy session bucket: ``_workspace/_agent/<segment>/`` when no binding role is available
    """
    from runtime.skills import default_skills_root

    base = Path(skills_home).resolve() if skills_home else default_skills_root().resolve()
    ws = base / "_workspace"
    if public:
        return ws / "public"
    role = str(workspace_lane_role or "").strip().lower()
    if role:
        return ws / fs_safe_workspace_lane_segment(role)
    owner = str(workspace_owner_session_id or "").strip()
    sid = str(session_id or "").strip()
    if not owner and not sid:
        return ws
    seg = workspace_lane_segment(workspace_owner_session_id=owner or None, session_id=sid or None)
    return ws / "_agent" / seg


def skills_home_containing_workspace_lane(install_skills_parent: Path) -> Path:
    """Resolve the skills tree root (parent of ``_workspace``) from a workspace lane install parent."""
    cur = Path(install_skills_parent).resolve()
    if cur.name.lower() == "_workspace":
        return cur.parent
    for anc in cur.parents:
        if anc.name.lower() == "_workspace":
            return anc.parent
    return cur


__all__ = [
    "fs_safe_workspace_lane_segment",
    "resolve_auto_install_parent",
    "skill_dir_private_lane_segment",
    "skills_home_containing_workspace_lane",
    "workspace_lane_segment",
]
