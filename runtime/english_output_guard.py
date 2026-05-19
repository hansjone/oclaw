from __future__ import annotations

ENGLISH_ONLY_OUTPUT_GUARD = """
## English-only output (mandatory)
- Session language is **English**. All user-visible text (titles, tables, bullets, summaries) must be **English only**.
- **Forbidden**: any Chinese / Japanese / Korean characters (CJK) in the reply. Do not paste Chinese from tools, skills, or prior messages.
- Tool and UME alarm fields may be Chinese in the source; **translate or paraphrase into English** before presenting. Keep ASCII identifiers (severity, IP, alarm key, host_name) as-is.
- If a vendor term cannot be translated confidently, use a short English description in brackets, e.g. `[link down alarm]` — still **no CJK**.
""".strip()


def english_output_guard_for_lang(lang: str) -> str:
    if str(lang or "").strip().lower().startswith("en"):
        return ENGLISH_ONLY_OUTPUT_GUARD
    return ""


__all__ = ["ENGLISH_ONLY_OUTPUT_GUARD", "english_output_guard_for_lang"]
