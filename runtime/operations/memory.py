from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def _now_date() -> dt.date:
    return dt.date.today()


def _iso_week_label(day: dt.date) -> str:
    year, week, _weekday = day.isocalendar()
    return f"{year}-W{week:02d}"


def _ensure_dirs(base_dir: Path) -> None:
    for name in ("Projects", "Areas", "Resources", "Archives", "Inbox", "runs"):
        (base_dir / name).mkdir(parents=True, exist_ok=True)


def _count_notes(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for item in path.rglob("*.md"):
        if item.name.lower() == "readme.md":
            continue
        if "templates" in item.parts or "runs" in item.parts:
            continue
        count += 1
    return count


def _recommend_new_cards(inbox_count: int, backlog_count: int, fresh_resources: int) -> int:
    target = 10
    if backlog_count > 0:
        target -= min(6, backlog_count // 20)
    if inbox_count > 20:
        target -= 2
    if fresh_resources >= 5 and backlog_count < 20:
        target += 1
    return max(3, min(10, target))


def _build_focus_order(projects: int, areas: int, resources: int) -> list[str]:
    ranked = [("Projects", projects * 3), ("Areas", areas * 2), ("Resources", resources)]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [name for name, score in ranked if score > 0][:3]


def _parse_date(text: str | None) -> dt.date:
    if not text:
        return _now_date()
    return dt.date.fromisoformat(text)


def _cmd_memory_status(args: argparse.Namespace) -> int:
    base = Path(args.base_dir).resolve()
    _ensure_dirs(base)
    projects = _count_notes(base / "Projects")
    areas = _count_notes(base / "Areas")
    resources = _count_notes(base / "Resources")
    archives = _count_notes(base / "Archives")
    inbox = _count_notes(base / "Inbox")
    suggested = _recommend_new_cards(inbox, int(args.review_backlog), resources)
    focus = _build_focus_order(projects, areas, resources)
    print(f"base_dir={base}")
    print(f"projects={projects} areas={areas} resources={resources} archives={archives} inbox={inbox}")
    print(f"suggested_new_cards_per_day={suggested}")
    print("focus_topics=" + (",".join(focus) if focus else "Resources"))
    return 0


def _cmd_memory_daily(args: argparse.Namespace) -> int:
    base = Path(args.base_dir).resolve()
    _ensure_dirs(base)
    day = _parse_date(args.date)
    projects = _count_notes(base / "Projects")
    areas = _count_notes(base / "Areas")
    resources = _count_notes(base / "Resources")
    inbox = _count_notes(base / "Inbox")
    suggested = _recommend_new_cards(inbox, int(args.review_backlog), resources)
    focus = _build_focus_order(projects, areas, resources)
    focus_topic = args.focus or (focus[0] if focus else "Resources")
    out = base / "runs" / f"daily-{day.isoformat()}.md"
    text = (
        f"# Daily Memory Run ({day.isoformat()})\n\n"
        f"- Focus topic: `{focus_topic}`\n"
        f"- Suggested new cards today: `{suggested}`\n"
        f"- Current inbox notes: `{inbox}`\n"
        f"- Review backlog input: `{int(args.review_backlog)}`\n\n"
        "## Auto Steps\n\n"
        "1. Capture 3-5 high-value items into `Inbox`.\n"
        "2. Distill 1-3 items into atomic notes under `Resources`.\n"
        "3. Convert notes into Q/A or cloze cards (respect suggested limit).\n"
        "4. Produce one output (summary/answer/code note).\n\n"
        "## Smart Suggestions\n\n"
        f"- Priority order now: `{', '.join(focus) if focus else 'Resources'}`\n"
        "- If reviews feel overloaded, reduce new cards before skipping due reviews.\n"
        "- If inbox keeps growing for 2+ days, process inbox first before new captures.\n"
    )
    out.write_text(text, encoding="utf-8")
    print(f"created={out}")
    return 0


def _cmd_memory_weekly(args: argparse.Namespace) -> int:
    base = Path(args.base_dir).resolve()
    _ensure_dirs(base)
    day = _parse_date(args.date)
    week_label = _iso_week_label(day)
    projects = _count_notes(base / "Projects")
    areas = _count_notes(base / "Areas")
    resources = _count_notes(base / "Resources")
    archives = _count_notes(base / "Archives")
    inbox = _count_notes(base / "Inbox")
    suggested = _recommend_new_cards(inbox, int(args.review_backlog), resources)
    focus = _build_focus_order(projects, areas, resources)
    out = base / "runs" / f"weekly-{week_label}.md"
    text = (
        f"# Weekly Memory Review ({week_label})\n\n"
        f"- Run date: `{day.isoformat()}`\n"
        f"- Suggested next-week new cards/day: `{suggested}`\n\n"
        "## Snapshot\n\n"
        f"- Projects notes: `{projects}`\n"
        f"- Areas notes: `{areas}`\n"
        f"- Resources notes: `{resources}`\n"
        f"- Archives notes: `{archives}`\n"
        f"- Inbox notes: `{inbox}`\n\n"
        "## Fixed Review Checklist\n\n"
        "- [ ] Inbox zero\n- [ ] Linking/backlinks completion\n- [ ] Move inactive notes to Archives\n- [ ] Tune next-week card load\n\n"
        "## Auto Focus for Next Week\n\n"
        f"- Top topics: `{', '.join(focus) if focus else 'Resources'}`\n"
        "- Keep new cards within 3-10/day and adjust by real review pressure.\n"
    )
    out.write_text(text, encoding="utf-8")
    print(f"created={out}")
    return 0


def register_memory_parser(root_sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    memory = root_sub.add_parser("memory", help="Memory system automation")
    memory_sub = memory.add_subparsers(dest="memory_cmd", required=True)

    status = memory_sub.add_parser("status", help="Show memory workload status")
    status.add_argument("--base-dir", default="docs/memory-system", help="Memory system base directory")
    status.add_argument("--review-backlog", type=int, default=0, help="Current due review backlog")
    status.set_defaults(func=_cmd_memory_status)

    daily = memory_sub.add_parser("daily", help="Generate today's automated memory run")
    daily.add_argument("--base-dir", default="docs/memory-system", help="Memory system base directory")
    daily.add_argument("--date", default=None, help="Run date in YYYY-MM-DD")
    daily.add_argument("--focus", default=None, help="Override focus topic")
    daily.add_argument("--review-backlog", type=int, default=0, help="Current due review backlog")
    daily.set_defaults(func=_cmd_memory_daily)

    weekly = memory_sub.add_parser("weekly", help="Generate weekly review run sheet")
    weekly.add_argument("--base-dir", default="docs/memory-system", help="Memory system base directory")
    weekly.add_argument("--date", default=None, help="Run date in YYYY-MM-DD")
    weekly.add_argument("--review-backlog", type=int, default=0, help="Current due review backlog")
    weekly.set_defaults(func=_cmd_memory_weekly)
