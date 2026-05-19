import unittest
from unittest import mock

from runtime.lang import detect_text_lang, resolve_runtime_lang


class ResolveRuntimeLangTests(unittest.TestCase):
    def test_user_text_english_overrides_ui_zh(self) -> None:
        store = mock.Mock()
        store.get_setting.return_value = "zh"
        self.assertEqual(
            resolve_runtime_lang(
                store=store,
                hint="zh",
                user_text="Please tally the current alarm information",
            ),
            "en",
        )

    def test_hint_when_text_ambiguous(self) -> None:
        store = mock.Mock()
        store.get_setting.return_value = "zh"
        self.assertEqual(resolve_runtime_lang(store=store, hint="en"), "en")

    def test_store_ui_lang(self) -> None:
        store = mock.Mock()
        store.get_setting.return_value = "en"
        self.assertEqual(resolve_runtime_lang(store=store), "en")

    def test_invalid_falls_back_zh(self) -> None:
        store = mock.Mock()
        store.get_setting.return_value = "fr"
        self.assertEqual(resolve_runtime_lang(store=store), "zh")

    def test_detect_english(self) -> None:
        self.assertEqual(detect_text_lang("Please tally alarms"), "en")

    def test_detect_chinese(self) -> None:
        self.assertEqual(detect_text_lang("请统计当前告警信息"), "zh")


if __name__ == "__main__":
    unittest.main()
