from __future__ import annotations

from oclaw.runtime.agents.specialists import default_system_prefix_for_specialist


def test_specialist_prompts_loaded_from_oclaw_tree() -> None:
    ops = default_system_prefix_for_specialist("ops", "zh")
    gen = default_system_prefix_for_specialist("generalist", "zh")
    assert "运维专家（ops specialist）" in ops
    assert "通识专家（generalist specialist）" in gen
