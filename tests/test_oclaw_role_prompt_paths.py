from __future__ import annotations

from oclaw.runtime.agents.specialists import default_system_prefix_for_specialist


def test_specialist_prompts_loaded_from_oclaw_tree() -> None:
    ops = default_system_prefix_for_specialist("ops", "zh")
    gen = default_system_prefix_for_specialist("generalist", "zh")
    img = default_system_prefix_for_specialist("image", "zh")
    assert "网络运维专家" in ops
    assert "通识专家" in gen
    assert "图像处理专家" in img
