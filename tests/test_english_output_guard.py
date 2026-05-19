import unittest

from runtime.english_output_guard import english_output_guard_for_lang


class EnglishOutputGuardTests(unittest.TestCase):
    def test_en_returns_guard(self) -> None:
        g = english_output_guard_for_lang("en")
        self.assertIn("English-only", g)
        self.assertIn("CJK", g)

    def test_zh_empty(self) -> None:
        self.assertEqual(english_output_guard_for_lang("zh"), "")


if __name__ == "__main__":
    unittest.main()
