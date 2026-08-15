from __future__ import annotations

import unittest
from datetime import date
from importlib.metadata import PackageNotFoundError, version


try:
    version("apache-airflow")
except PackageNotFoundError:
    AIRFLOW_AVAILABLE = False
else:
    AIRFLOW_AVAILABLE = True


@unittest.skipUnless(AIRFLOW_AVAILABLE, "Airflow 전용 환경에서 실행하는 DAG 테스트")
class RetailDailyIngestionDagTest(unittest.TestCase):
    """첫 DAG가 수동 날짜와 task 순서를 안전하게 정의하는지 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        from dags.retail_daily_ingestion import (
            parse_target_date,
            retail_daily_ingestion_dag,
        )

        cls.dag = retail_daily_ingestion_dag
        cls.parse_target_date = staticmethod(parse_target_date)

    def test_has_manual_schedule_and_expected_tasks(self) -> None:
        """자동 catchup 없이 날짜 검증 뒤 일일 pipeline을 실행해야 한다."""
        self.assertEqual(self.dag.dag_id, "retail_daily_ingestion")
        self.assertIsNone(self.dag.schedule)
        self.assertFalse(self.dag.catchup)
        self.assertEqual(
            set(self.dag.task_ids),
            {"resolve_target_date", "load_and_validate_daily_sales"},
        )
        self.assertEqual(
            self.dag.get_task("resolve_target_date").downstream_task_ids,
            {"load_and_validate_daily_sales"},
        )

    def test_accepts_iso_target_date(self) -> None:
        """정상 ISO 날짜는 Python date로 변환해야 한다."""
        self.assertEqual(
            self.parse_target_date("2009-12-01"),
            date(2009, 12, 1),
        )

    def test_rejects_invalid_target_date(self) -> None:
        """잘못된 날짜를 다른 날짜로 추측하지 않고 실행 전에 거부해야 한다."""
        with self.assertRaisesRegex(ValueError, "올바른 날짜"):
            self.parse_target_date("2009-13-01")
