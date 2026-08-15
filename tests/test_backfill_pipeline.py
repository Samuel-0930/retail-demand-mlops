from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.backfill_pipeline import (
    BackfillDateRangeError,
    run_backfill_pipeline,
)
from retail_demand_mlops.ingestion.daily_pipeline import DailyPipelineResult
from retail_demand_mlops.ingestion.loader import IngestionRunResult, LoadResult
from retail_demand_mlops.ingestion.validate import DailyLoadValidationReport


class BackfillPipelineTest(unittest.TestCase):
    """backfill이 유효한 날짜만 순서대로 처리하고 실패를 숨기지 않는지 확인한다."""

    def setUp(self) -> None:
        self.settings = DatabaseSettings(
            host="localhost",
            port=5432,
            database="retail_demand",
            user="retail_app",
            password="",
        )
        self.csv_path = Path("sales.csv")
        self.manifest_path = Path("manifest.json")

    def _daily_result(self, target_date: date, run_id: int) -> DailyPipelineResult:
        """호출 순서와 집계를 검증할 최소 일일 결과를 만든다."""
        return DailyPipelineResult(
            ingestion=IngestionRunResult(
                run_id=run_id,
                load_result=LoadResult(
                    input_rows=3,
                    inserted_rows=3,
                    skipped_rows=0,
                ),
            ),
            validation=DailyLoadValidationReport(
                target_date=target_date,
                expected_rows=3,
                actual_rows=3,
                first_source_row=1,
                last_source_row=3,
                anonymous_rows=1,
                cancellation_rows=0,
                return_rows=0,
            ),
        )

    @patch("retail_demand_mlops.ingestion.backfill_pipeline.run_daily_pipeline")
    def test_runs_inclusive_date_range_in_order(self, run_daily_pipeline) -> None:
        """시작일과 종료일을 모두 포함해 하루씩 날짜순으로 실행해야 한다."""
        start_date = date(2009, 12, 1)
        end_date = date(2009, 12, 3)
        run_daily_pipeline.side_effect = [
            self._daily_result(date(2009, 12, 1), 1),
            self._daily_result(date(2009, 12, 2), 2),
            self._daily_result(date(2009, 12, 3), 3),
        ]

        result = run_backfill_pipeline(
            self.settings,
            start_date,
            end_date,
            self.csv_path,
            self.manifest_path,
        )

        self.assertEqual(len(result.daily_results), 3)
        self.assertEqual(
            [call.args[1] for call in run_daily_pipeline.call_args_list],
            [date(2009, 12, 1), date(2009, 12, 2), date(2009, 12, 3)],
        )

    @patch("retail_demand_mlops.ingestion.backfill_pipeline.run_daily_pipeline")
    def test_stops_after_daily_failure(self, run_daily_pipeline) -> None:
        """실패 뒤 날짜를 계속 처리해 부분 실패를 성공처럼 보이게 하지 않아야 한다."""
        run_daily_pipeline.side_effect = [
            self._daily_result(date(2009, 12, 1), 1),
            RuntimeError("daily load failed"),
        ]

        with self.assertRaisesRegex(RuntimeError, "daily load failed"):
            run_backfill_pipeline(
                self.settings,
                date(2009, 12, 1),
                date(2009, 12, 3),
                self.csv_path,
                self.manifest_path,
            )

        self.assertEqual(run_daily_pipeline.call_count, 2)

    @patch("retail_demand_mlops.ingestion.backfill_pipeline.run_daily_pipeline")
    def test_rejects_reversed_date_range(self, run_daily_pipeline) -> None:
        """시작일이 더 늦으면 어떤 일일 적재도 시작하지 않아야 한다."""
        with self.assertRaisesRegex(BackfillDateRangeError, "시작일"):
            run_backfill_pipeline(
                self.settings,
                date(2009, 12, 2),
                date(2009, 12, 1),
                self.csv_path,
                self.manifest_path,
            )

        run_daily_pipeline.assert_not_called()
