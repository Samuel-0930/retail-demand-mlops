from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from retail_demand_mlops.ingestion.simulator import (
    SimulationDataError,
    iter_daily_sales,
)


class IterDailySalesTest(unittest.TestCase):
    """날짜별 판매 데이터 추출기의 정상 동작과 입력 오류 처리를 검증한다."""

    def setUp(self) -> None:
        # 각 테스트가 독립적인 CSV를 사용하도록 임시 디렉터리를 새로 만든다.
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.source_path = Path(self.temporary_directory.name) / "sales.csv"

    def test_yields_only_rows_for_target_date(self) -> None:
        """여러 날짜가 섞인 CSV에서 요청 날짜의 행만 반환해야 한다."""
        self.source_path.write_text(
            "date,product_id,quantity,price\n"
            "2024-01-01,101,2,10.50\n"
            "2024-01-02,101,3,10.50\n"
            "2024-01-02,202,1,8.00\n",
            encoding="utf-8",
        )

        rows = list(iter_daily_sales(self.source_path, date(2024, 1, 2)))

        self.assertEqual([row["product_id"] for row in rows], ["101", "202"])

    def test_rejects_csv_without_configured_date_column(self) -> None:
        """설정한 날짜 컬럼이 없으면 불완전한 배치를 만들지 않아야 한다."""
        self.source_path.write_text(
            "sold_at,product_id\n2024-01-01,101\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SimulationDataError, "missing the date column"):
            list(iter_daily_sales(self.source_path, date(2024, 1, 1)))

    def test_rejects_invalid_date_in_source(self) -> None:
        """해석할 수 없는 날짜를 발견하면 해당 행을 조용히 무시하지 않아야 한다."""
        self.source_path.write_text(
            "date,product_id\nnot-a-date,101\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SimulationDataError, "Invalid ISO date"):
            list(iter_daily_sales(self.source_path, date(2024, 1, 1)))


if __name__ == "__main__":
    # 이 테스트 파일을 직접 실행하는 경우에도 unittest가 동작하게 한다.
    unittest.main()
