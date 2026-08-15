from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock

from retail_demand_mlops.ingestion.status import (
    IngestionRunRecord,
    IngestionStatusQueryError,
    format_ingestion_runs,
    list_recent_ingestion_runs,
)


class IngestionStatusTest(unittest.TestCase):
    """최근 실행 조회가 읽기 전용 정보만 정확한 순서로 전달하는지 확인한다."""

    def test_returns_recent_runs_from_database_rows(self) -> None:
        """데이터베이스 결과를 운영 화면에 필요한 타입으로 변환해야 한다."""
        started_at = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
        finished_at = datetime(2026, 8, 15, 10, 1, tzinfo=timezone.utc)
        connection = Mock()
        connection.execute.return_value.fetchall.return_value = [
            (
                7,
                date(2009, 12, 1),
                "succeeded",
                3223,
                0,
                3223,
                None,
                started_at,
                finished_at,
            )
        ]

        records = list_recent_ingestion_runs(connection, limit=5)

        self.assertEqual(records[0].run_id, 7)
        self.assertEqual(records[0].skipped_rows, 3223)
        self.assertEqual(connection.execute.call_args.args[1], (5,))

    def test_rejects_limit_outside_safe_range(self) -> None:
        """과도하거나 의미 없는 조회 개수는 SQL 실행 전에 거부해야 한다."""
        connection = Mock()

        with self.assertRaisesRegex(IngestionStatusQueryError, "1~100"):
            list_recent_ingestion_runs(connection, limit=0)

        connection.execute.assert_not_called()

    def test_formats_nulls_and_multiline_error_as_one_row(self) -> None:
        """실행 중이거나 실패한 기록도 표의 한 행을 깨뜨리지 않아야 한다."""
        records = (
            IngestionRunRecord(
                run_id=8,
                batch_date=None,
                status="failed",
                input_rows=None,
                inserted_rows=None,
                skipped_rows=None,
                error_message="ValueError: invalid\nrow",
                started_at=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 8, 15, 10, 1, tzinfo=timezone.utc),
            ),
        )

        output = format_ingestion_runs(records)

        self.assertEqual(len(output.splitlines()), 2)
        self.assertIn("ValueError: invalid row", output)
        self.assertIn("\t-\tfailed\t", output)
