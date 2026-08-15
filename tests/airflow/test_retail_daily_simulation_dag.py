from __future__ import annotations

import os
import unittest
from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch


try:
    version("apache-airflow")
except PackageNotFoundError:
    AIRFLOW_AVAILABLE = False
else:
    AIRFLOW_AVAILABLE = True


SIMULATION_ENVIRONMENT = {
    "RETAIL_SIMULATION_SCHEDULE_START_DATE": "2026-08-16",
    "RETAIL_SIMULATION_SOURCE_START_DATE": "2009-12-01",
    "RETAIL_SIMULATION_SOURCE_END_DATE": "2011-12-09",
}


@unittest.skipUnless(AIRFLOW_AVAILABLE, "Airflow 전용 환경에서 실행하는 DAG 테스트")
class RetailDailySimulationDagTest(unittest.TestCase):
    """자동 일일 DAG가 pause 상태와 data interval timetable을 사용하는지 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        with patch.dict(os.environ, SIMULATION_ENVIRONMENT):
            from dags.retail_daily_simulation import (
                resolve_simulation_target_date,
                retail_daily_simulation_dag,
            )

        cls.dag = retail_daily_simulation_dag
        cls.resolve_simulation_target_date = staticmethod(
            resolve_simulation_target_date
        )

    def test_uses_daily_data_interval_and_starts_paused(self) -> None:
        """전역 cron 설정과 무관한 일일 구간을 쓰고 최초 자동 실행을 막아야 한다."""
        from airflow.timetables.interval import CronDataIntervalTimetable

        self.assertEqual(self.dag.dag_id, "retail_daily_simulation")
        self.assertIsInstance(self.dag.timetable, CronDataIntervalTimetable)
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertTrue(self.dag.is_paused_upon_creation)
        self.assertEqual(
            self.dag.start_date.in_timezone("Asia/Seoul").date().isoformat(),
            "2026-08-16",
        )
        self.assertEqual(
            self.dag.end_date.in_timezone("Asia/Seoul").date().isoformat(),
            "2028-08-23",
        )

    def test_resolves_interval_before_loading_daily_sales(self) -> None:
        """data interval 매핑 성공 뒤에만 기존 일일 pipeline을 실행해야 한다."""
        self.assertEqual(
            set(self.dag.task_ids),
            {"resolve_simulation_target_date", "load_simulated_daily_sales"},
        )
        self.assertEqual(
            self.dag.get_task("resolve_simulation_target_date").downstream_task_ids,
            {"load_simulated_daily_sales"},
        )

    def test_maps_interval_start_to_historical_sale_date(self) -> None:
        """서울 기준 일정 셋째 날은 원본 판매 셋째 날로 연결해야 한다."""
        import pendulum

        self.assertEqual(
            self.resolve_simulation_target_date(
                pendulum.datetime(2026, 8, 18, tz="Asia/Seoul")
            ),
            "2009-12-03",
        )
