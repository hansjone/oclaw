from __future__ import annotations

import unittest

from runtime.application.gateway.inbound_service import _parse_schedule_duration_seconds


class ScheduleDurationParseTests(unittest.TestCase):
    def test_minutes(self) -> None:
        self.assertEqual(_parse_schedule_duration_seconds("5分钟"), 300)

    def test_hours(self) -> None:
        self.assertEqual(_parse_schedule_duration_seconds("1小时"), 3600)

    def test_seconds(self) -> None:
        self.assertEqual(_parse_schedule_duration_seconds("120秒"), 120)


if __name__ == "__main__":
    unittest.main()
