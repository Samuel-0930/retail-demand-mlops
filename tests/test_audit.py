from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import Mock

from retail_demand_mlops.ingestion.audit import (
    fail_ingestion_run,
    start_ingestion_run,
    succeed_ingestion_run,
)
from retail_demand_mlops.ingestion.loader import LoadResult


class IngestionAuditTest(unittest.TestCase):
    """적재 실행 이력이 running에서 성공 또는 실패로 전환되는지 검증한다."""

    def test_starts_run_and_returns_database_id(self) -> None:
        """실행 시작 시 데이터베이스가 생성한 run_id를 호출자에게 반환해야 한다."""
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = (42,)

        run_id = start_ingestion_run(
            connection,
            "a" * 64,
            date(2009, 12, 1),
        )

        self.assertEqual(run_id, 42)

    def test_marks_run_as_succeeded_with_row_counts(self) -> None:
        """성공 이력에는 입력·삽입·중복 행 수가 모두 기록돼야 한다."""
        connection = Mock()
        connection.execute.return_value.rowcount = 1

        succeed_ingestion_run(
            connection,
            42,
            LoadResult(input_rows=10, inserted_rows=7, skipped_rows=3),
        )

        parameters = connection.execute.call_args.args[1]
        self.assertEqual(parameters, (10, 7, 3, 42))

    def test_marks_run_as_failed_with_error_type(self) -> None:
        """실패 이력은 예외 타입과 메시지를 남겨 원인 추적을 가능하게 해야 한다."""
        connection = Mock()
        connection.execute.return_value.rowcount = 1

        fail_ingestion_run(connection, 42, ValueError("invalid row"))

        parameters = connection.execute.call_args.args[1]
        self.assertEqual(parameters, ("ValueError: invalid row", 42))


if __name__ == "__main__":
    unittest.main()
