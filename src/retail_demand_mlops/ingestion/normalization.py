"""UCI 원본 거래 한 행을 내부 표준 판매 스키마로 정규화한다."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Mapping


CANONICAL_SALES_COLUMNS: Final[tuple[str, ...]] = (
    "invoice_id",
    "stock_code",
    "description",
    "quantity",
    "invoice_datetime",
    "date",
    "unit_price",
    "customer_id",
    "country",
    "is_customer_identified",
    "is_cancellation",
    "is_return",
    "is_zero_price",
    "is_negative_price",
)

REQUIRED_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
)


class TransactionNormalizationError(ValueError):
    """원본 행을 손실 없이 표준 판매 레코드로 바꿀 수 없을 때의 예외."""


def validate_source_columns(columns: tuple[Any, ...]) -> None:
    """원본 XLSX 헤더가 정규화 계약을 충족하는지 변환 전에 확인한다."""
    normalized_columns = tuple(str(column).strip() for column in columns)
    if normalized_columns != REQUIRED_SOURCE_COLUMNS:
        raise TransactionNormalizationError(
            "원본 컬럼이 예상 스키마와 일치하지 않습니다: "
            f"expected={REQUIRED_SOURCE_COLUMNS}, actual={normalized_columns}"
        )


def _required_text(value: Any, field_name: str) -> str:
    """필수 식별자와 문자열을 공백 없는 텍스트로 보존한다."""
    if value is None:
        raise TransactionNormalizationError(f"필수 값이 없습니다: {field_name}")
    text = str(value).strip()
    if not text:
        raise TransactionNormalizationError(f"필수 값이 비어 있습니다: {field_name}")
    return text


def _integer_text(value: Any, field_name: str) -> str:
    """수량처럼 소수점을 허용하지 않는 값을 정수 문자열로 변환한다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransactionNormalizationError(f"정수가 아닌 값입니다: {field_name}={value!r}")
    if isinstance(value, float) and not value.is_integer():
        raise TransactionNormalizationError(f"정수가 아닌 값입니다: {field_name}={value!r}")
    return str(int(value))


def _decimal_text(value: Any, field_name: str) -> tuple[str, Decimal]:
    """부동소수점 표현 오차를 확대하지 않고 가격을 십진수 문자열로 바꾼다."""
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TransactionNormalizationError(
            f"십진수가 아닌 값입니다: {field_name}={value!r}"
        ) from error
    if not decimal_value.is_finite():
        raise TransactionNormalizationError(
            f"유한한 십진수가 아닙니다: {field_name}={value!r}"
        )
    return format(decimal_value, "f"), decimal_value


def normalize_transaction(source_row: Mapping[str, Any]) -> dict[str, str]:
    """원본 거래를 CSV와 PostgreSQL에서 공통으로 쓸 문자열 레코드로 변환한다.

    고객 ID 결측은 빈 문자열과 식별 여부 플래그로 보존한다. 취소·반품·가격
    이상도 제거하지 않고 별도 플래그로 표현해 후속 사용 목적에 따라 선택한다.
    """
    invoice_id = _required_text(source_row.get("Invoice"), "Invoice")
    stock_code = _required_text(source_row.get("StockCode"), "StockCode")
    description_value = source_row.get("Description")
    description = "" if description_value is None else str(description_value).strip()
    quantity_text = _integer_text(source_row.get("Quantity"), "Quantity")
    quantity = int(quantity_text)

    invoice_datetime = source_row.get("InvoiceDate")
    if not isinstance(invoice_datetime, datetime):
        raise TransactionNormalizationError(
            f"거래 시각이 datetime이 아닙니다: InvoiceDate={invoice_datetime!r}"
        )

    unit_price, decimal_price = _decimal_text(source_row.get("Price"), "Price")
    customer_value = source_row.get("Customer ID")
    customer_id = "" if customer_value is None else _integer_text(customer_value, "Customer ID")
    country = _required_text(source_row.get("Country"), "Country")

    # 문자열 플래그는 CSV로 저장한 뒤에도 데이터베이스 적재 시 명확히 변환할 수 있다.
    return {
        "invoice_id": invoice_id,
        "stock_code": stock_code,
        "description": description,
        "quantity": quantity_text,
        "invoice_datetime": invoice_datetime.isoformat(timespec="seconds"),
        "date": invoice_datetime.date().isoformat(),
        "unit_price": unit_price,
        "customer_id": customer_id,
        "country": country,
        "is_customer_identified": str(bool(customer_id)).lower(),
        "is_cancellation": str(invoice_id.upper().startswith("C")).lower(),
        "is_return": str(quantity < 0).lower(),
        "is_zero_price": str(decimal_price == 0).lower(),
        "is_negative_price": str(decimal_price < 0).lower(),
    }
