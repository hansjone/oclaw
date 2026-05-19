import unittest
from unittest import mock

from runtime.lang import resolve_runtime_lang


class ResolveRuntimeLangTests(unittest.TestCase):
    def test_hint_wins(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
