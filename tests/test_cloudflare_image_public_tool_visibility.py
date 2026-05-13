from __future__ import annotations

from runtime.tools.catalog import default_registry


def test_cloudflare_image_generate_in_public_registry() -> None:
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "cloudflare_image_generate" in names

