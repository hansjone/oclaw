from __future__ import annotations

from pathlib import Path
import re

DIARY_START_MARKER = "<!-- openclaw:dreaming:diary:start -->"
DIARY_END_MARKER = "<!-- openclaw:dreaming:diary:end -->"
BACKFILL_ENTRY_MARKER = "openclaw:dreaming:backfill-entry"

def _resolve_dreams_path(workspace_dir: str) -> Path:
    base = Path(workspace_dir)
    upper = base / "DREAMS.md"
    lower = base / "dreams.md"
    if upper.exists():
        return upper
    if lower.exists():
        return lower
    return upper

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _split_diary_blocks(text: str) -> list[str]:
    return [b.strip() for b in text.split("\n---\n") if b.strip()]


def _ensure_diary_section(existing: str) -> str:
    if DIARY_START_MARKER in existing and DIARY_END_MARKER in existing:
        return existing
    section = f"# Dream Diary\n\n{DIARY_START_MARKER}\n{DIARY_END_MARKER}\n"
    return section if not existing.strip() else f"{section}\n{existing}"


def _replace_diary_content(existing: str, diary_content: str) -> str:
    ensured = _ensure_diary_section(existing)
    start_idx = ensured.find(DIARY_START_MARKER)
    end_idx = ensured.find(DIARY_END_MARKER)
    if start_idx < 0 or end_idx < 0 or end_idx < start_idx:
        return ensured
    before = ensured[: start_idx + len(DIARY_START_MARKER)]
    after = ensured[end_idx:]
    middle = f"\n{diary_content.strip()}\n" if diary_content.strip() else "\n"
    return before + middle + after


def _join_diary_blocks(blocks: list[str]) -> str:
    if not blocks:
        return ""
    return "\n".join([f"---\n\n{b.strip()}\n" for b in blocks]).strip() + "\n"


def write_backfill_diary_entries(*, workspace_dir: str, entries: list[dict], timezone: str | None = None) -> dict:
    _ = timezone
    dreams_path = _resolve_dreams_path(workspace_dir)
    existing = _read_text(dreams_path)
    ensured = _ensure_diary_section(existing)
    start_idx = ensured.find(DIARY_START_MARKER)
    end_idx = ensured.find(DIARY_END_MARKER)
    inner = ensured[start_idx + len(DIARY_START_MARKER) : end_idx] if start_idx >= 0 and end_idx > start_idx else ""
    kept = [b for b in _split_diary_blocks(inner) if BACKFILL_ENTRY_MARKER not in b]
    replaced = len(_split_diary_blocks(inner)) - len(kept)

    for entry in entries:
        iso_day = str(entry.get("isoDay") or "").strip()
        body_lines = entry.get("bodyLines") or []
        source_path = str(entry.get("sourcePath") or "").strip()
        marker = f"<!-- {BACKFILL_ENTRY_MARKER} day={iso_day}{(' source=' + source_path) if source_path else ''} -->"
        body = "\n".join(str(x).rstrip() for x in body_lines).strip()
        block = f"*{iso_day or 'unknown-day'}*\n\n{marker}\n\n{body}".strip()
        kept.append(block)

    updated = _replace_diary_content(ensured, _join_diary_blocks(kept))
    dreams_path.parent.mkdir(parents=True, exist_ok=True)
    dreams_path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
    return {"dreamsPath": str(dreams_path), "written": len(entries), "replaced": replaced}


def remove_backfill_diary_entries(*, workspace_dir: str) -> dict:
    dreams_path = _resolve_dreams_path(workspace_dir)
    existing = _read_text(dreams_path)
    ensured = _ensure_diary_section(existing)
    start_idx = ensured.find(DIARY_START_MARKER)
    end_idx = ensured.find(DIARY_END_MARKER)
    inner = ensured[start_idx + len(DIARY_START_MARKER) : end_idx] if start_idx >= 0 and end_idx > start_idx else ""
    blocks = _split_diary_blocks(inner)
    kept = [b for b in blocks if BACKFILL_ENTRY_MARKER not in b]
    removed = len(blocks) - len(kept)
    if removed > 0:
        updated = _replace_diary_content(ensured, _join_diary_blocks(kept))
        dreams_path.parent.mkdir(parents=True, exist_ok=True)
        dreams_path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
    return {"dreamsPath": str(dreams_path), "removed": removed}


def dedupe_dream_diary_entries(*, workspace_dir: str) -> dict:
    dreams_path = _resolve_dreams_path(workspace_dir)
    existing = _read_text(dreams_path)
    ensured = _ensure_diary_section(existing)
    start_idx = ensured.find(DIARY_START_MARKER)
    end_idx = ensured.find(DIARY_END_MARKER)
    inner = ensured[start_idx + len(DIARY_START_MARKER) : end_idx] if start_idx >= 0 and end_idx > start_idx else ""
    blocks = _split_diary_blocks(inner)
    seen: set[str] = set()
    kept: list[str] = []
    for b in blocks:
        key = "\n".join(line.strip() for line in b.splitlines() if line.strip() and not line.strip().startswith("<!--"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(b)
    removed = len(blocks) - len(kept)
    if removed > 0:
        updated = _replace_diary_content(ensured, _join_diary_blocks(kept))
        dreams_path.parent.mkdir(parents=True, exist_ok=True)
        dreams_path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
    return {"dreamsPath": str(dreams_path), "removed": removed, "kept": len(kept)}


def preview_grounded_rem_markdown(*, workspace_dir: str, input_paths: list[str]) -> dict:
    workspace = Path(workspace_dir).resolve()

    # ---- Grounded REM heuristics (ported/simplified from vendor/openclaw memory-core) ----
    blocked_section_re = re.compile(
        r"\b(morning reminders|tasks? for today|to-?do|action items?|next steps?|stats|setup tasks?)\b",
        re.I,
    )
    generic_section_re = re.compile(r"^(setup|session notes?|notes|summary)$", re.I)
    memory_signal_re = re.compile(r"\b(always use|prefers?|preference|standing rule|rule:|remember)\b", re.I)
    build_signal_re = re.compile(r"\b(set up|setup|created|built|rewrite|rewrote|implemented|installed|configured|added|updated|documented)\b", re.I)
    incident_signal_re = re.compile(r"\b(fail(?:ed|ing)?|error|issue|problem|auth|expired|broken|unable|missing|required|root cause)\b", re.I)
    logistics_signal_re = re.compile(r"\b(flight|calendar|reservation|schedule|travel|pickup|address|hotel)\b", re.I)
    task_signal_re = re.compile(r"\b(reminder|task|to-?do|action item|next step|need to|follow up)\b", re.I)
    routing_signal_re = re.compile(r"\b(route|routing|workflow|processor|read later|auto-implement|codex)\b", re.I)
    externalization_signal_re = re.compile(r"\b(obsidian|memory|tracker|notes captured|updated .*md|documented)\b", re.I)

    code_fence_re = re.compile(r"^\s*```")
    table_re = re.compile(r"^\s*\|.*\|\s*$")
    table_divider_re = re.compile(r"^\s*\|?[\s:-]+\|[\s|:-]*$")
    time_prefix_re = re.compile(r"^\d{1,2}:\d{2}\s*-\s*")

    def normalize_path(raw_path: str) -> str:
        return raw_path.replace("\\", "/").lstrip("./")

    def normalize_ws(text: str) -> str:
        return " ".join((text or "").strip().split())

    def strip_markdown(text: str) -> str:
        s = text or ""
        s = re.sub(r"!\[[^\]]*]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", s)
        s = re.sub(r"[`*_~>#]", "", s)
        return normalize_ws(s)

    def sanitize_title(title: str) -> str:
        return normalize_ws(strip_markdown(time_prefix_re.sub("", title or "")))

    def make_ref(path_value: str, start_line: int, end_line: int | None = None) -> str:
        end_line = start_line if end_line is None else end_line
        return f"{path_value}:{start_line}" if start_line == end_line else f"{path_value}:{start_line}-{end_line}"

    def parse_markdown_sections(content: str) -> list[dict]:
        lines = (content or "").splitlines()
        sections: list[dict] = []
        current: dict | None = None
        in_code_fence = False

        def flush() -> None:
            nonlocal current
            if not current:
                return
            meaningful = [x for x in current["lines"] if normalize_ws(x["text"])]
            if meaningful:
                current["lines"] = meaningful
                current["endLine"] = meaningful[-1]["line"]
                sections.append(current)
            current = None

        for idx, raw in enumerate(lines, start=1):
            if code_fence_re.match(raw):
                in_code_fence = not in_code_fence
                continue
            if in_code_fence:
                continue
            m = re.match(r"^\s{0,3}(#{2,6})\s+(.+)$", raw)
            if m:
                flush()
                current = {"title": sanitize_title(m.group(2)), "startLine": idx, "endLine": idx, "lines": []}
                continue
            if not current:
                continue
            current["endLine"] = idx
            trimmed = raw.strip()
            if (
                not trimmed
                or re.fullmatch(r"---+", trimmed)
                or table_re.match(trimmed)
                or table_divider_re.match(trimmed)
            ):
                continue
            current["lines"].append({"line": idx, "text": raw})
        flush()
        return sections

    def section_to_snippets(section: dict) -> list[dict]:
        snippets: list[dict] = []
        seen: set[str] = set()
        for entry in section.get("lines") or []:
            raw = str(entry.get("text") or "").strip()
            if not raw:
                continue
            m = re.match(r"^(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.*)$", raw)
            candidate = m.group(1) if m else raw
            text = normalize_ws(strip_markdown(candidate))
            if len(text) < 10:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            snippets.append({"text": text, "line": int(entry.get("line") or 0) or 1})
        return snippets

    def score_section(title: str, snippets: list[dict]) -> dict:
        def count(pattern: re.Pattern[str]) -> int:
            return sum(1 for s in snippets if pattern.search(s["text"]))

        preference = count(memory_signal_re) + (1 if memory_signal_re.search(title) else 0)
        build = count(build_signal_re) + (1 if build_signal_re.search(title) else 0)
        incident = count(incident_signal_re) + (1 if incident_signal_re.search(title) else 0)
        logistics = count(logistics_signal_re) + (1 if logistics_signal_re.search(title) else 0)
        tasks = count(task_signal_re) + (1 if task_signal_re.search(title) else 0)
        routing = count(routing_signal_re) + (1 if routing_signal_re.search(title) else 0)
        externalization = count(externalization_signal_re) + (1 if externalization_signal_re.search(title) else 0)
        overall = (
            preference * 2.0
            + build * 1.6
            + incident * 1.6
            + logistics * 1.2
            + routing * 1.8
            + externalization * 1.4
            + min(len(snippets), 3) * 0.3
            - (0.8 if generic_section_re.search(title) else 0.0)
        )
        return {
            "preference": preference,
            "build": build,
            "incident": incident,
            "logistics": logistics,
            "tasks": tasks,
            "routing": routing,
            "externalization": externalization,
            "overall": overall,
        }

    def summarize_section(path_value: str, section: dict) -> dict | None:
        title = sanitize_title(str(section.get("title") or ""))
        if blocked_section_re.search(title):
            return None
        snippets = section_to_snippets(section)
        if not snippets:
            return None
        # pick up to 3 best snippets by memory/build/routing signals
        def snippet_score(text: str) -> float:
            score = 1.0
            if memory_signal_re.search(text):
                score += 2.2
            if routing_signal_re.search(text):
                score += 1.4
            if externalization_signal_re.search(text):
                score += 1.1
            if build_signal_re.search(text):
                score += 1.2
            if incident_signal_re.search(text):
                score += 1.2
            if task_signal_re.search(text) and not build_signal_re.search(text):
                score -= 0.8
            return score

        selected = sorted(snippets, key=lambda s: (-snippet_score(s["text"]), s["line"]))[: (2 if generic_section_re.search(title) else 3)]
        selected = sorted(selected, key=lambda s: s["line"])
        body = "; ".join(s["text"] for s in selected)
        text = body if (not title or generic_section_re.search(title)) else f"{title}: {body}"
        return {
            "title": title,
            "text": text,
            "refs": [make_ref(path_value, s["line"]) for s in selected],
            "scores": score_section(title, snippets),
        }

    def preview_for_file(*, rel_path: str, content: str) -> dict:
        sections = parse_markdown_sections(content)
        summaries = [s for s in (summarize_section(rel_path, sec) for sec in sections) if s]

        facts = []
        used = set()
        for summary in sorted(summaries, key=lambda x: -(x["scores"]["overall"])):
            key = summary["text"].lower()
            if key in used:
                continue
            used.add(key)
            facts.append({"text": summary["text"], "refs": summary["refs"]})
            if len(facts) >= 4:
                break

        memory_implications = [
            {"text": s["text"].split(":", 1)[-1].strip(), "refs": s["refs"]}
            for s in summaries
            if s["scores"]["preference"] > 0
        ][:3]

        candidates = []
        for item in memory_implications:
            candidates.append({"text": item["text"], "refs": item["refs"], "lean": "likely_durable"})
        candidates = candidates[:4]

        reflections = []
        if memory_implications:
            reflections.append(
                {
                    "text": "A stable rule or preference appears explicitly, which suggests durable memory updates may be warranted.",
                    "refs": (memory_implications[0]["refs"] if memory_implications else []),
                }
            )
        if not facts and sections:
            reflections.append(
                {
                    "text": "No grounded facts were extracted from this note yet.",
                    "refs": [make_ref(rel_path, sections[0]["startLine"], sections[-1]["endLine"])],
                }
            )
        reflections = reflections[:4]

        rendered_lines = ["## What Happened"]
        if not facts:
            rendered_lines.append("1. No grounded facts were extracted.")
        else:
            for idx, fact in enumerate(facts, start=1):
                rendered_lines.append(f"{idx}. {fact['text']} [{', '.join(fact['refs'])}]")
        rendered_lines.append("")
        rendered_lines.append("## Reflections")
        if not reflections:
            rendered_lines.append("1. No grounded reflections emerged from this note yet.")
        else:
            for idx, ref in enumerate(reflections, start=1):
                rendered_lines.append(f"{idx}. {ref['text']} [{', '.join(ref['refs'])}]")
        if candidates:
            rendered_lines.append("")
            rendered_lines.append("## Candidates")
            for cand in candidates:
                rendered_lines.append(f"- [{cand['lean']}] {cand['text']} [{', '.join(cand['refs'])}]")
        if memory_implications:
            rendered_lines.append("")
            rendered_lines.append("## Possible Lasting Updates")
            for imp in memory_implications:
                rendered_lines.append(f"- {imp['text']} [{', '.join(imp['refs'])}]")

        return {
            "path": rel_path,
            "facts": facts,
            "reflections": reflections,
            "memoryImplications": memory_implications,
            "candidates": candidates,
            "renderedMarkdown": "\n".join(rendered_lines),
        }

    def iter_md_files() -> list[Path]:
        found: list[Path] = []
        for raw in input_paths:
            if not str(raw or "").strip():
                continue
            p = Path(raw)
            if not p.is_absolute():
                p = (workspace / p).resolve()
            if p.is_file() and p.suffix.lower() == ".md":
                found.append(p)
            elif p.is_dir():
                found.extend(sorted(p.rglob("*.md")))
        # stabilize, dedupe
        uniq: dict[str, Path] = {}
        for p in found:
            try:
                key = str(p.resolve())
            except Exception:
                key = str(p)
            uniq[key] = p
        return [uniq[k] for k in sorted(uniq.keys())]

    previews: list[dict] = []
    for md_path in iter_md_files():
        content = _read_text(md_path)
        try:
            rel = (
                normalize_path(str(md_path.resolve().relative_to(workspace.resolve())))
                if md_path.resolve().is_relative_to(workspace.resolve())
                else normalize_path(str(md_path))
            )
        except Exception:
            rel = normalize_path(str(md_path))
        previews.append(preview_for_file(rel_path=rel, content=content))

    return {"workspaceDir": str(workspace), "scannedFiles": len(previews), "files": previews}
