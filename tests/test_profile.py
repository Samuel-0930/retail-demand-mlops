from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from retail_demand_mlops.ingestion.download import calculate_sha256
from retail_demand_mlops.ingestion.profile import profile_workbook


class ProfileWorkbookTest(unittest.TestCase):
    """읽기 전용 프로파일러의 스키마와 품질 집계를 검증한다."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.source_path = Path(self.temporary_directory.name) / "sample.xlsx"

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Sales"
        worksheet.append(
            [
                "Invoice",
                "StockCode",
                "Description",
                "Quantity",
                "InvoiceDate",
                "Price",
                "Customer ID",
                "Country",
            ]
        )
        worksheet.append(
            ["100001", 1001, "Item", 2, datetime(2024, 1, 1, 10), 3.5, 10, "UK"]
        )
        worksheet.append(
            ["C100002", "A1", None, -1, datetime(2024, 1, 2, 11), 0, 10, "UK"]
        )
        worksheet.append(
            ["C100002", "A1", None, -1, datetime(2024, 1, 2, 11), 0, 10, "UK"]
        )
        workbook.save(self.source_path)

    def test_profiles_schema_quality_and_preserves_source(self) -> None:
        """집계 결과가 정확하고 프로파일링 전후 원본 체크섬이 같아야 한다."""
        checksum_before = calculate_sha256(self.source_path)

        report = profile_workbook(self.source_path)

        checksum_after = calculate_sha256(self.source_path)
        sheet = report["sheets"][0]
        columns = {column["name"]: column for column in sheet["columns"]}
        self.assertEqual(checksum_before, checksum_after)
        self.assertEqual(report["total_row_count"], 3)
        self.assertEqual(columns["Description"]["null_count"], 2)
        self.assertEqual(columns["InvoiceDate"]["minimum"], "2024-01-01T10:00:00")
        self.assertNotIn("minimum", columns["StockCode"])
        self.assertEqual(sheet["quality"]["duplicate_row_count"], 1)
        self.assertEqual(sheet["quality"]["cancellation_row_count"], 2)
        self.assertEqual(sheet["quality"]["negative_quantity_count"], 2)
        self.assertEqual(sheet["quality"]["zero_price_count"], 2)


if __name__ == "__main__":
    unittest.main()
