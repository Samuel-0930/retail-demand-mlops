from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from retail_demand_mlops.ingestion.normalization import CANONICAL_SALES_COLUMNS
from retail_demand_mlops.ingestion.validate import (
    LoadValidationError,
    validate_loaded_date,
    validate_loaded_source,
)


class ValidateLoadedSourceTest(unittest.TestCase):
    """manifest와 PostgreSQL 집계의 일치 및 불일치 판정을 검증한다."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.manifest_path = Path(self.temporary_directory.name) / "manifest.json"
        self.manifest_path.write_text(
            json.dumps(
                {
                    "target_sha256": "a" * 64,
                    "columns": list(CANONICAL_SALES_COLUMNS),
                    "row_count": 3,
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _connection_with_result(result: tuple[object, ...]) -> Mock:
        """검증 로직에 필요한 PostgreSQL 집계 한 행만 반환하는 연결을 만든다."""
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = result
        return connection

    def test_returns_quality_report_when_load_matches_manifest(self) -> None:
        """행 수와 행 번호 범위가 일치하면 품질 지표 보고서를 반환해야 한다."""
        connection = self._connection_with_result(
            (3, 1, 3, date(2009, 12, 1), date(2009, 12, 2), 1, 1, 1, 0, 0)
        )

        report = validate_loaded_source(connection, self.manifest_path)

        self.assertEqual(report.actual_rows, 3)
        self.assertEqual(report.anonymous_rows, 1)
        self.assertEqual(report.first_sale_date, date(2009, 12, 1))

    def test_rejects_missing_database_rows(self) -> None:
        """일부 행이 빠지면 행 수와 마지막 출처 행 번호 불일치를 알려야 한다."""
        connection = self._connection_with_result(
            (2, 1, 2, date(2009, 12, 1), date(2009, 12, 1), 0, 0, 0, 0, 0)
        )

        with self.assertRaisesRegex(LoadValidationError, "행 수 expected=3, actual=2"):
            validate_loaded_source(connection, self.manifest_path)

    @patch("retail_demand_mlops.ingestion.validate.iter_daily_ingestion_rows")
    def test_validates_target_date_source_row_range(self, daily_rows: Mock) -> None:
        """하루치 기대 행 수와 첫·마지막 원본 행 번호가 모두 일치해야 한다."""
        daily_rows.return_value = [("a" * 64, 10), ("a" * 64, 11)]
        connection = self._connection_with_result((2, 10, 11, 1, 0, 0))

        report = validate_loaded_date(
            connection,
            Path("sales.csv"),
            self.manifest_path,
            date(2009, 12, 1),
        )

        self.assertEqual(report.expected_rows, 2)
        self.assertEqual(report.first_source_row, 10)
        self.assertEqual(report.last_source_row, 11)

    @patch("retail_demand_mlops.ingestion.validate.iter_daily_ingestion_rows")
    def test_rejects_incomplete_target_date(self, daily_rows: Mock) -> None:
        """날짜별 PostgreSQL 행이 하나라도 빠지면 배치 검증을 실패해야 한다."""
        daily_rows.return_value = [("a" * 64, 10), ("a" * 64, 11)]
        connection = self._connection_with_result((1, 10, 10, 0, 0, 0))

        with self.assertRaisesRegex(
            LoadValidationError,
            "2009-12-01 날짜 배치 검증 실패",
        ):
            validate_loaded_date(
                connection,
                Path("sales.csv"),
                self.manifest_path,
                date(2009, 12, 1),
            )


if __name__ == "__main__":
    unittest.main()
