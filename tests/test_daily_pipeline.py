from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.daily_pipeline import run_daily_pipeline
from retail_demand_mlops.ingestion.loader import IngestionRunResult, LoadResult
from retail_demand_mlops.ingestion.validate import (
    DailyLoadValidationReport,
    LoadValidationError,
)


class DailyPipelineTest(unittest.TestCase):
    """일일 pipeline이 적재 후 검증을 실행하고 실패를 숨기지 않는지 확인한다."""

    def setUp(self) -> None:
        self.settings = DatabaseSettings(
            host="localhost",
            port=5432,
            database="retail_demand",
            user="retail_app",
            password="",
        )
        self.target_date = date(2009, 12, 1)
        self.csv_path = Path("sales.csv")
        self.manifest_path = Path("manifest.json")

    @patch("retail_demand_mlops.ingestion.daily_pipeline.psycopg.connect")
    @patch("retail_demand_mlops.ingestion.daily_pipeline.validate_loaded_date")
    @patch("retail_demand_mlops.ingestion.daily_pipeline.run_ingestion")
    def test_runs_ingestion_before_validation(
        self,
        run_ingestion,
        validate_loaded_date,
        connect,
    ) -> None:
        """한 날짜의 적재 결과를 만든 뒤 같은 날짜를 검증해야 한다."""
        run_ingestion.return_value = IngestionRunResult(
            run_id=7,
            load_result=LoadResult(input_rows=3, inserted_rows=3, skipped_rows=0),
        )
        validate_loaded_date.return_value = DailyLoadValidationReport(
            target_date=self.target_date,
            expected_rows=3,
            actual_rows=3,
            first_source_row=1,
            last_source_row=3,
            anonymous_rows=1,
            cancellation_rows=0,
            return_rows=0,
        )

        result = run_daily_pipeline(
            self.settings,
            self.target_date,
            self.csv_path,
            self.manifest_path,
        )

        self.assertEqual(result.ingestion.run_id, 7)
        self.assertEqual(result.validation.actual_rows, 3)
        run_ingestion.assert_called_once_with(
            self.settings,
            self.csv_path,
            self.manifest_path,
            target_date=self.target_date,
        )
        validate_loaded_date.assert_called_once()

    @patch("retail_demand_mlops.ingestion.daily_pipeline.psycopg.connect")
    @patch("retail_demand_mlops.ingestion.daily_pipeline.validate_loaded_date")
    @patch("retail_demand_mlops.ingestion.daily_pipeline.run_ingestion")
    def test_propagates_validation_failure(
        self,
        run_ingestion,
        validate_loaded_date,
        connect,
    ) -> None:
        """적재 후 검증 실패를 성공으로 출력하지 않고 호출자에게 전달해야 한다."""
        run_ingestion.return_value = IngestionRunResult(
            run_id=8,
            load_result=LoadResult(input_rows=3, inserted_rows=3, skipped_rows=0),
        )
        validate_loaded_date.side_effect = LoadValidationError("missing row")

        with self.assertRaisesRegex(LoadValidationError, "missing row"):
            run_daily_pipeline(
                self.settings,
                self.target_date,
                self.csv_path,
                self.manifest_path,
            )
