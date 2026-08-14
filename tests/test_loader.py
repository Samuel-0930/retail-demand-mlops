from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from retail_demand_mlops.ingestion.download import calculate_sha256
from retail_demand_mlops.ingestion.loader import (
    DatasetLoadError,
    iter_daily_ingestion_rows,
    iter_ingestion_rows,
)
from retail_demand_mlops.ingestion.normalization import CANONICAL_SALES_COLUMNS


class IterIngestionRowsTest(unittest.TestCase):
    """CSV 무결성, 타입 변환, 행 번호 생성을 PostgreSQL 없이 검증한다."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root_path = Path(self.temporary_directory.name)
        self.csv_path = root_path / "sales.csv"
        self.manifest_path = root_path / "sales.csv.manifest.json"
        self.rows = [
            {
                "invoice_id": "536365",
                "stock_code": "85123A",
                "description": "Item",
                "quantity": "6",
                "invoice_datetime": "2010-12-01T08:26:00",
                "date": "2010-12-01",
                "unit_price": "2.55",
                "customer_id": "",
                "country": "United Kingdom",
                "is_customer_identified": "false",
                "is_cancellation": "false",
                "is_return": "false",
                "is_zero_price": "false",
                "is_negative_price": "false",
            }
        ]
        self._write_files()

    def _write_files(self) -> None:
        """테스트 행과 일치하는 체크섬·행 수 manifest를 함께 생성한다."""
        with self.csv_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CANONICAL_SALES_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        manifest = {
            "target_sha256": calculate_sha256(self.csv_path),
            "columns": list(CANONICAL_SALES_COLUMNS),
            "row_count": len(self.rows),
        }
        self.manifest_path.write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    def test_converts_csv_values_and_assigns_source_identity(self) -> None:
        """체크섬과 1부터 시작하는 행 번호가 타입 변환된 값과 함께 생성돼야 한다."""
        ingestion_row = list(iter_ingestion_rows(self.csv_path, self.manifest_path))[0]

        self.assertEqual(ingestion_row[0], calculate_sha256(self.csv_path))
        self.assertEqual(ingestion_row[1], 1)
        self.assertEqual(ingestion_row[5], 6)
        self.assertEqual(ingestion_row[6], datetime(2010, 12, 1, 8, 26))
        self.assertEqual(ingestion_row[7], date(2010, 12, 1))
        self.assertEqual(ingestion_row[8], Decimal("2.55"))
        self.assertIsNone(ingestion_row[9])
        self.assertFalse(ingestion_row[11])

    def test_rejects_csv_changed_after_manifest_creation(self) -> None:
        """manifest 생성 후 수정된 CSV는 적재를 시작하기 전에 거부해야 한다."""
        with self.csv_path.open("a", encoding="utf-8") as csv_file:
            csv_file.write("corrupted\n")

        with self.assertRaisesRegex(DatasetLoadError, "체크섬이 manifest와"):
            list(iter_ingestion_rows(self.csv_path, self.manifest_path))

    def test_rejects_manifest_row_count_mismatch(self) -> None:
        """CSV가 잘렸거나 행이 추가되면 전체 순회 후 행 수 불일치를 알려야 한다."""
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["row_count"] = 2
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaisesRegex(DatasetLoadError, "CSV 행 수가 manifest와"):
            list(iter_ingestion_rows(self.csv_path, self.manifest_path))

    def test_yields_only_rows_for_target_date(self) -> None:
        """날짜별 배치는 전체 CSV 계약을 검증하면서 요청 날짜만 반환해야 한다."""
        second_row = dict(self.rows[0])
        second_row["invoice_id"] = "536366"
        second_row["invoice_datetime"] = "2010-12-02T09:00:00"
        second_row["date"] = "2010-12-02"
        self.rows.append(second_row)
        self._write_files()

        ingestion_rows = list(
            iter_daily_ingestion_rows(
                self.csv_path,
                self.manifest_path,
                date(2010, 12, 2),
            )
        )

        self.assertEqual(len(ingestion_rows), 1)
        self.assertEqual(ingestion_rows[0][2], "536366")
        self.assertEqual(ingestion_rows[0][7], date(2010, 12, 2))


if __name__ == "__main__":
    unittest.main()
