from __future__ import annotations

import unittest
from datetime import datetime

from retail_demand_mlops.ingestion.normalization import (
    REQUIRED_SOURCE_COLUMNS,
    TransactionNormalizationError,
    normalize_transaction,
    validate_source_columns,
)


class NormalizeTransactionTest(unittest.TestCase):
    """원본 거래의 정상·익명·취소 행이 표준 계약을 지키는지 검증한다."""

    def setUp(self) -> None:
        self.source_row = {
            "Invoice": 536365,
            "StockCode": "85123A",
            "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
            "Quantity": 6,
            "InvoiceDate": datetime(2010, 12, 1, 8, 26),
            "Price": 2.55,
            "Customer ID": 17850,
            "Country": "United Kingdom",
        }

    def test_normalizes_identified_sale(self) -> None:
        """식별된 정상 판매는 날짜와 문자열 식별자를 손실 없이 만들어야 한다."""
        normalized = normalize_transaction(self.source_row)

        self.assertEqual(normalized["invoice_id"], "536365")
        self.assertEqual(normalized["date"], "2010-12-01")
        self.assertEqual(normalized["unit_price"], "2.55")
        self.assertEqual(normalized["customer_id"], "17850")
        self.assertEqual(normalized["is_customer_identified"], "true")
        self.assertEqual(normalized["is_cancellation"], "false")

    def test_preserves_anonymous_sale_without_fake_customer(self) -> None:
        """고객 ID 결측은 삭제하거나 공통 가짜 ID로 치환하지 않아야 한다."""
        self.source_row["Customer ID"] = None

        normalized = normalize_transaction(self.source_row)

        self.assertEqual(normalized["customer_id"], "")
        self.assertEqual(normalized["is_customer_identified"], "false")

    def test_marks_cancellation_return_and_zero_price(self) -> None:
        """취소·반품·무료 행을 제거하지 않고 각각 독립된 플래그로 표시해야 한다."""
        self.source_row["Invoice"] = "C536365"
        self.source_row["Quantity"] = -1
        self.source_row["Price"] = 0

        normalized = normalize_transaction(self.source_row)

        self.assertEqual(normalized["is_cancellation"], "true")
        self.assertEqual(normalized["is_return"], "true")
        self.assertEqual(normalized["is_zero_price"], "true")

    def test_rejects_non_datetime_invoice_date(self) -> None:
        """날짜를 추측해 변환하지 않고 원본 계약 위반을 명시적으로 알려야 한다."""
        self.source_row["InvoiceDate"] = "2010-12-01 08:26:00"

        with self.assertRaisesRegex(TransactionNormalizationError, "datetime이 아닙니다"):
            normalize_transaction(self.source_row)


class ValidateSourceColumnsTest(unittest.TestCase):
    """전체 변환 전에 원본 헤더 변경을 탐지하는 계약을 검증한다."""

    def test_accepts_profiled_uci_columns(self) -> None:
        """현재 프로파일에서 확인한 8개 컬럼은 허용해야 한다."""
        validate_source_columns(REQUIRED_SOURCE_COLUMNS)

    def test_rejects_changed_source_columns(self) -> None:
        """컬럼명이나 순서가 달라지면 잘못 매핑하기 전에 중단해야 한다."""
        with self.assertRaisesRegex(TransactionNormalizationError, "일치하지 않습니다"):
            validate_source_columns(("InvoiceNo",))


if __name__ == "__main__":
    unittest.main()
