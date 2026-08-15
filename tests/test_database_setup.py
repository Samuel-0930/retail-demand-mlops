from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from retail_demand_mlops.database.setup import (
    DatabaseSetupError,
    apply_schema,
    discover_sql_files,
)


class DatabaseSetupTest(unittest.TestCase):
    """DDL 파일 탐색 순서와 부분 적용 방지에 필요한 예외 전달을 검증한다."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.sql_directory = Path(self.temporary_directory.name)

    def test_discovers_only_numbered_sql_files_in_order(self) -> None:
        """파일 생성 순서와 관계없이 번호순 DDL만 선택해야 한다."""
        (self.sql_directory / "002_second.sql").write_text("SELECT 2;", encoding="utf-8")
        (self.sql_directory / "README.md").write_text("ignored", encoding="utf-8")
        (self.sql_directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")

        sql_files = discover_sql_files(self.sql_directory)

        self.assertEqual(
            [sql_file.name for sql_file in sql_files],
            ["001_first.sql", "002_second.sql"],
        )

    def test_applies_sql_in_discovered_order(self) -> None:
        """하나의 연결에서 SQL 내용을 번호순으로 실행해야 한다."""
        (self.sql_directory / "002_second.sql").write_text("SELECT 2;", encoding="utf-8")
        (self.sql_directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
        connection = Mock()

        applied_files = apply_schema(connection, self.sql_directory)

        self.assertEqual(applied_files, ("001_first.sql", "002_second.sql"))
        self.assertEqual(
            [call.args[0] for call in connection.execute.call_args_list],
            ["SELECT 1;", "SELECT 2;"],
        )

    def test_rejects_directory_without_numbered_sql(self) -> None:
        """적용할 DDL이 없는데 성공으로 오인하지 않아야 한다."""
        with self.assertRaisesRegex(DatabaseSetupError, "적용할 SQL 파일이 없습니다"):
            discover_sql_files(self.sql_directory)

    def test_propagates_sql_execution_failure(self) -> None:
        """DDL 오류를 숨기지 않아 CLI 연결 context가 전체를 rollback하게 해야 한다."""
        (self.sql_directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
        (self.sql_directory / "002_second.sql").write_text("INVALID;", encoding="utf-8")
        connection = Mock()
        connection.execute.side_effect = [None, RuntimeError("invalid SQL")]

        with self.assertRaisesRegex(RuntimeError, "invalid SQL"):
            apply_schema(connection, self.sql_directory)


if __name__ == "__main__":
    unittest.main()
