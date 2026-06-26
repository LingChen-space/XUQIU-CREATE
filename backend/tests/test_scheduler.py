"""每日调度补偿测试。"""

import unittest
from datetime import datetime

from app.services.scheduler import should_run_daily_catchup


class SchedulerCatchupTest(unittest.TestCase):
    def test_after_schedule_without_report_should_catch_up(self):
        now = datetime(2026, 6, 26, 9, 0)

        self.assertTrue(
            should_run_daily_catchup(
                now=now,
                schedule_hour=6,
                schedule_minute=0,
                has_today_report=False,
                pipeline_running=False,
            )
        )

    def test_before_schedule_should_not_catch_up(self):
        now = datetime(2026, 6, 26, 5, 59)

        self.assertFalse(
            should_run_daily_catchup(
                now=now,
                schedule_hour=6,
                schedule_minute=0,
                has_today_report=False,
                pipeline_running=False,
            )
        )

    def test_existing_report_should_not_catch_up(self):
        now = datetime(2026, 6, 26, 9, 0)

        self.assertFalse(
            should_run_daily_catchup(
                now=now,
                schedule_hour=6,
                schedule_minute=0,
                has_today_report=True,
                pipeline_running=False,
            )
        )

    def test_running_pipeline_should_not_start_another_catchup(self):
        now = datetime(2026, 6, 26, 9, 0)

        self.assertFalse(
            should_run_daily_catchup(
                now=now,
                schedule_hour=6,
                schedule_minute=0,
                has_today_report=False,
                pipeline_running=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
