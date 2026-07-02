from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.scheduler.system_timezone import (
    default_system_timezone,
    reset_default_system_timezone_cache,
)
from zoneinfo import ZoneInfo


class SchedulerSystemTimezoneTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_default_system_timezone_cache()
        os.environ.pop("AIA_SCHEDULER_DEFAULT_TIMEZONE", None)
        os.environ.pop("TZ", None)

    def test_env_override_wins(self) -> None:
        os.environ["AIA_SCHEDULER_DEFAULT_TIMEZONE"] = "Europe/Berlin"
        reset_default_system_timezone_cache()
        self.assertEqual(default_system_timezone(), "Europe/Berlin")

    def test_windows_registry_maps_to_iana(self) -> None:
        with patch("runtime.scheduler.system_timezone.sys.platform", "win32"), patch(
            "runtime.scheduler.system_timezone._windows_system_timezone",
            return_value="Asia/Jakarta",
        ):
            reset_default_system_timezone_cache()
            self.assertEqual(default_system_timezone(), "Asia/Jakarta")

    def test_default_is_valid_iana(self) -> None:
        tz = default_system_timezone()
        ZoneInfo(tz)


if __name__ == "__main__":
    unittest.main()
