from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from retail_demand_mlops.ingestion.normalization import REQUIRED_SOURCE_COLUMNS
from retail_demand_mlops.ingestion.transform import convert_workbook_to_csv


class ConvertWorkbookToCsvTest(unittest.TestCase):
    """시트 병합, 중복 구간 제거, 재실행 검증을 작은 워크북으로 확인한다."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root_path = Path(self.temporary_directory.name)
        self.source_path = root_path / "source.xlsx"
        self.target_path = root_path / "processed" / "sales.csv"
        self.manifest_path = root_path / "processed" / "sales.csv.manifest.json"

        workbook = Workbook()
        first_sheet = workbook.active
        first_sheet.title = "First"
        first_sheet.append(REQUIRED_SOURCE_COLUMNS)
        first_row = self._row(1, datetime(2024, 1, 1, 9))
        duplicated_row = self._row(2, datetime(2024, 1, 2, 9))
        first_sheet.append(first_row)
        first_sheet.append(duplicated_row)
        # 같은 시트 안의 동일 행은 원본 거래 사실일 수 있으므로 그대로 보존한다.
        first_sheet.append(duplicated_row)

        second_sheet = workbook.create_sheet("Second")
        second_sheet.append(REQUIRED_SOURCE_COLUMNS)
        second_sheet.append(duplicated_row)
        second_sheet.append(duplicated_row)
        second_sheet.append(self._row(3, datetime(2024, 1, 3, 9)))
        workbook.save(self.source_path)

    @staticmethod
    def _row(invoice: int, invoice_datetime: datetime) -> tuple[object, ...]:
        """테스트가 병합 동작에 집중하도록 유효한 원본 행을 일관되게 만든다."""
        return (
            invoice,
            "A1",
            "Item",
            1,
            invoice_datetime,
            2.5,
            10,
            "United Kingdom",
        )

    def test_skips_only_cross_sheet_overlap(self) -> None:
        """시트 간 겹침은 제거하되 첫 시트 내부의 동일 행은 보존해야 한다."""
        result = convert_workbook_to_csv(
            self.source_path,
            self.target_path,
            self.manifest_path,
        )

        with self.target_path.open(encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
        self.assertTrue(result.created)
        self.assertEqual(result.row_count, 4)
        self.assertEqual(result.skipped_overlap_count, 2)
        self.assertEqual([row["invoice_id"] for row in rows], ["1", "2", "2", "3"])

    def test_reuses_verified_existing_output(self) -> None:
        """원본과 출력 체크섬이 같으면 두 번째 실행에서 CSV를 다시 쓰지 않아야 한다."""
        convert_workbook_to_csv(
            self.source_path,
            self.target_path,
            self.manifest_path,
        )
        modified_time = self.target_path.stat().st_mtime_ns

        result = convert_workbook_to_csv(
            self.source_path,
            self.target_path,
            self.manifest_path,
        )

        self.assertFalse(result.created)
        self.assertEqual(result.row_count, 4)
        self.assertEqual(self.target_path.stat().st_mtime_ns, modified_time)


if __name__ == "__main__":
    unittest.main()
