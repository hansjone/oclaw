from __future__ import annotations

import platform

from runtime.hooks.config import should_include_hook
from runtime.hooks.eligibility_from_metadata import hook_eligibility_from_message_metadata
from runtime.hooks.hook_types import HookEntry, HookInvocation, HookRef


def _entry(*, name: str = "x", bins: tuple[str, ...] = (), os_list: tuple[str, ...] = ()) -> HookEntry:
    md: dict = {
        "events": ["a:b"],
        "requires": {"bins": list(bins)},
    }
    if os_list:
        md["os"] = list(os_list)
    return HookEntry(
        hook=HookRef(
            name=name,
            description="",
            source="oclaw-workspace",
            pluginId=None,
            filePath="/x/HOOK.md",
            baseDir="/x",
            handlerPath="/x/handler.py",
        ),
        frontmatter={},
        metadata=md,
        invocation=HookInvocation(enabled=True),
    )


def test_hook_eligibility_from_metadata_none_when_absent() -> None:
    assert hook_eligibility_from_message_metadata(None) is None
    assert hook_eligibility_from_message_metadata({}) is None
    assert hook_eligibility_from_message_metadata({"hookEligibility": {}}) is None
    assert hook_eligibility_from_message_metadata({"hookEligibility": {"remote": {}}}) is None


def test_hook_eligibility_from_metadata_bins_present_predicates() -> None:
    elig = hook_eligibility_from_message_metadata(
        {"hookEligibility": {"remote": {"binsPresent": ["git", "node"]}}},
    )
    assert elig is not None
    remote = elig.get("remote") or {}
    assert remote["hasBin"]("git") is True
    assert remote["hasBin"]("node") is True
    assert remote["hasBin"]("missing-tool-xyz") is False
    assert remote["hasAnyBin"](["a", "git"]) is True
    assert remote["hasAnyBin"](["a", "b"]) is False


def test_hook_eligibility_from_metadata_platforms_lowercased() -> None:
    elig = hook_eligibility_from_message_metadata(
        {"hookEligibility": {"remote": {"platforms": ["Darwin", "LINUX"]}}},
    )
    assert elig is not None
    assert elig["remote"]["platforms"] == ["darwin", "linux"]


def test_hook_eligibility_from_metadata_note_only() -> None:
    elig = hook_eligibility_from_message_metadata({"hookEligibility": {"remote": {"note": " agent-a "}}})
    assert elig is not None
    assert elig["remote"]["note"] == "agent-a"


def test_should_include_hook_respects_bins_present_remote() -> None:
    entry = _entry(name="needs-git", bins=("git",))
    cfg = {"hooks": {"internal": {"enabled": True, "entries": {"needs-git": {"enabled": True}}}}}
    assert should_include_hook(entry=entry, config=cfg, eligibility=None) is (True if __import__("shutil").which("git") else False)

    elig = hook_eligibility_from_message_metadata(
        {"hookEligibility": {"remote": {"binsPresent": ["fantasy-bin-oclaw-test"]}}},
    )
    assert elig is not None
    assert should_include_hook(entry=entry, config=cfg, eligibility=elig) is False

    elig_ok = hook_eligibility_from_message_metadata({"hookEligibility": {"remote": {"binsPresent": ["git"]}}})
    assert elig_ok is not None
    assert should_include_hook(entry=entry, config=cfg, eligibility=elig_ok) is True


def test_should_include_hook_remote_platforms_satisfy_os_allowlist_when_local_differs() -> None:
    entry = _entry(name="linux-only", bins=(), os_list=("linux",))
    cfg = {"hooks": {"internal": {"enabled": True, "entries": {"linux-only": {"enabled": True}}}}}

    cur = platform.system().lower()
    if cur == "linux":
        assert should_include_hook(entry=entry, config=cfg, eligibility=None) is True
    else:
        assert should_include_hook(entry=entry, config=cfg, eligibility=None) is False

    elig = hook_eligibility_from_message_metadata({"hookEligibility": {"remote": {"platforms": ["linux"]}}})
    assert elig is not None
    # OpenClaw semantics: remote platform list can satisfy hook ``os`` even when this process runs elsewhere.
    assert should_include_hook(entry=entry, config=cfg, eligibility=elig) is True
