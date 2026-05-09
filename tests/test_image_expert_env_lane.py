"""Image specialist lane must use ``AIA_IMAGE_EXPERT_*``, not ``AIA_OCR_*``."""

from __future__ import annotations

from oclaw.platform.llm.image_legacy_client import send_legacy_image_messages


def test_legacy_fails_when_only_ocr_env_configured(monkeypatch: object) -> None:
    monkeypatch.setenv("AIA_OCR_API_KEY", "k-ocr")
    monkeypatch.setenv("AIA_OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("AIA_OCR_MODEL", "ocr-model")
    for k in ("AIA_IMAGE_EXPERT_API_KEY", "AIA_IMAGE_EXPERT_BASE_URL", "AIA_IMAGE_EXPERT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    out = send_legacy_image_messages(
        images=["https://example.com/x.png"],
        prompt="hi",
        model=None,
        api_key=None,
        base_url=None,
    )
    assert out.get("ok") is False
    err = str(out.get("error") or "")
    assert "AIA_IMAGE_EXPERT" in err


def test_legacy_accepts_explicit_kwargs_without_expert_env(monkeypatch: object) -> None:
    """Explicit api_key/base_url/model override env (for scripts/tests only)."""
    for k in (
        "AIA_OCR_API_KEY",
        "AIA_OCR_BASE_URL",
        "AIA_IMAGE_EXPERT_API_KEY",
        "AIA_IMAGE_EXPERT_BASE_URL",
    ):
        monkeypatch.delenv(k, raising=False)

    recorded: dict[str, object] = {}

    def fake_post(client, *, url: str, headers: dict[str, str], payload: dict[str, object]) -> object:
        recorded["url"] = url

        class R:
            status_code = 200

            def json(_self):  # noqa: PLR6301
                return {"choices": [{"message": {"content": [{"text": "ok"}]}}]}

        return R()

    import oclaw.platform.llm.image_legacy_client as mod

    monkeypatch.setattr(mod, "post_with_retry", fake_post)
    out = send_legacy_image_messages(
        images=["https://example.com/x.png"],
        prompt="hello",
        model="m-special",
        api_key="explicit-key",
        base_url="https://gw.example/expert/v1",
    )
    assert out.get("ok") is True
    assert "/chat/completions" in str(recorded.get("url") or "")
