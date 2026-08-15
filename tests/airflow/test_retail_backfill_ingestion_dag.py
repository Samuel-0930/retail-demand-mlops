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
class RetailBackfillIngestionDagTest(unittest.TestCase):
    """소규모 backfill DAG가 최대 3일을 순서대로 처리하도록 제한하는지 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        from dags.retail_backfill_ingestion import (
            parse_backfill_date_range,
            retail_backfill_ingestion_dag,
        )

        cls.dag = retail_backfill_ingestion_dag
        cls.parse_backfill_date_range = staticmethod(parse_backfill_date_range)

    def test_has_manual_schedule_and_sequential_tasks(self) -> None:
        """자동 실행 없이 범위 검증 뒤 하나의 순차 backfill task를 실행해야 한다."""
        self.assertEqual(self.dag.dag_id, "retail_backfill_ingestion")
        self.assertIsNone(self.dag.schedule)
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertEqual(
            set(self.dag.task_ids),
            {"resolve_backfill_date_range", "run_sequential_backfill"},
        )
        self.assertEqual(
            self.dag.get_task("resolve_backfill_date_range").downstream_task_ids,
            {"run_sequential_backfill"},
        )

    def test_accepts_inclusive_three_day_range(self) -> None:
        """시작일과 종료일을 포함한 3일 범위까지 허용해야 한다."""
        self.assertEqual(
            self.parse_backfill_date_range("2009-12-01", "2009-12-03"),
            (date(2009, 12, 1), date(2009, 12, 3)),
        )

    def test_rejects_reversed_date_range(self) -> None:
        """시작일이 종료일보다 늦으면 실행 전에 거부해야 한다."""
        with self.assertRaisesRegex(ValueError, "시작일"):
            self.parse_backfill_date_range("2009-12-03", "2009-12-01")

    def test_rejects_range_longer_than_three_days(self) -> None:
        """실수로 큰 과거 범위를 실행하지 못하도록 4일 이상을 거부해야 한다."""
        with self.assertRaisesRegex(ValueError, "최대 3일"):
            self.parse_backfill_date_range("2009-12-01", "2009-12-04")

