from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from retail_demand_mlops.ingestion.normalization import CANONICAL_SALES_COLUMNS
from retail_demand_mlops.ingestion.validate import (
    LoadValidationError,
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


if __name__ == "__main__":
    unittest.main()
