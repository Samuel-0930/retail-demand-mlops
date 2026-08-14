"""표준 판매 CSV를 PostgreSQL raw 테이블에 멱등하게 적재한다."""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

import psycopg

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.audit import (
    fail_ingestion_run,
    start_ingestion_run,
    succeed_ingestion_run,
)
from retail_demand_mlops.ingestion.download import calculate_sha256
from retail_demand_mlops.ingestion.normalization import CANONICAL_SALES_COLUMNS
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


COPY_COLUMNS = (
    "source_file_sha256",
    "source_row_number",
    "invoice_id",
    "stock_code",
    "description",
    "quantity",
    "invoice_datetime",
    "sale_date",
    "unit_price",
    "customer_id",
    "country",
    "is_customer_identified",
    "is_cancellation",
    "is_return",
    "is_zero_price",
    "is_negative_price",
)
SALE_DATE_INDEX = COPY_COLUMNS.index("sale_date")


class DatasetLoadError(RuntimeError):
    """CSV를 신뢰할 수 있는 PostgreSQL 행으로 적재하지 못할 때의 예외."""


@dataclass(frozen=True)
class LoadResult:
    """한 번의 적재에서 입력·신규·중복 행 수를 구분해 전달한다."""

    input_rows: int
    inserted_rows: int
    skipped_rows: int


def read_csv_manifest(manifest_path: Path) -> dict[str, Any]:
    """CSV manifest의 필수 무결성 메타데이터를 읽고 계약을 검증한다."""
    if not manifest_path.exists():
        raise DatasetLoadError(f"CSV manifest가 없습니다: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetLoadError(f"CSV manifest를 읽을 수 없습니다: {manifest_path}") from error

    source_checksum = manifest.get("target_sha256")
    if not isinstance(source_checksum, str) or len(source_checksum) != 64:
        raise DatasetLoadError("manifest의 target_sha256이 올바르지 않습니다")
    if manifest.get("columns") != list(CANONICAL_SALES_COLUMNS):
        raise DatasetLoadError("manifest의 컬럼 계약이 현재 스키마와 일치하지 않습니다")
    expected_row_count = manifest.get("row_count")
    if not isinstance(expected_row_count, int) or expected_row_count < 0:
        raise DatasetLoadError("manifest의 row_count가 올바르지 않습니다")
    return manifest


def _parse_boolean(value: str, field_name: str) -> bool:
    """모호한 truthy 변환을 피하고 정규화된 true/false만 허용한다."""
    if value == "true":
        return True
    if value == "false":
        return False
    raise DatasetLoadError(f"boolean 값이 올바르지 않습니다: {field_name}={value!r}")


def _parse_row(
    row: dict[str, str],
    source_checksum: str,
    source_row_number: int,
) -> tuple[Any, ...]:
    """CSV 문자열을 PostgreSQL 컬럼 타입에 맞는 Python 값으로 변환한다."""
    try:
        quantity = int(row["quantity"])
        invoice_datetime = datetime.fromisoformat(row["invoice_datetime"])
        sale_date = date.fromisoformat(row["date"])
        unit_price = Decimal(row["unit_price"])
    except (KeyError, ValueError, InvalidOperation) as error:
        raise DatasetLoadError(
            f"CSV 데이터 타입 변환에 실패했습니다: row={source_row_number}"
        ) from error

    if not unit_price.is_finite():
        raise DatasetLoadError(f"가격이 유한한 값이 아닙니다: row={source_row_number}")

    return (
        source_checksum,
        source_row_number,
        row["invoice_id"],
        row["stock_code"],
        row["description"] or None,
        quantity,
        invoice_datetime,
        sale_date,
        unit_price,
        row["customer_id"] or None,
        row["country"],
        _parse_boolean(row["is_customer_identified"], "is_customer_identified"),
        _parse_boolean(row["is_cancellation"], "is_cancellation"),
        _parse_boolean(row["is_return"], "is_return"),
        _parse_boolean(row["is_zero_price"], "is_zero_price"),
        _parse_boolean(row["is_negative_price"], "is_negative_price"),
    )


def iter_ingestion_rows(
    csv_path: Path,
    manifest_path: Path,
) -> Iterator[tuple[Any, ...]]:
    """manifest로 CSV를 검증하고 COPY에 전달할 행을 한 줄씩 생성한다."""
    if not csv_path.exists():
        raise DatasetLoadError(f"표준 CSV가 없습니다: {csv_path}")
    manifest = read_csv_manifest(manifest_path)
    source_checksum = manifest["target_sha256"]
    if calculate_sha256(csv_path) != source_checksum:
        raise DatasetLoadError(f"CSV 체크섬이 manifest와 일치하지 않습니다: {csv_path}")

    expected_row_count = manifest["row_count"]

    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if tuple(reader.fieldnames or ()) != CANONICAL_SALES_COLUMNS:
            raise DatasetLoadError("CSV 헤더가 표준 판매 스키마와 일치하지 않습니다")

        actual_row_count = 0
        for source_row_number, row in enumerate(reader, start=1):
            actual_row_count = source_row_number
            try:
                yield _parse_row(row, source_checksum, source_row_number)
            except DatasetLoadError as error:
                raise DatasetLoadError(
                    f"CSV 행 검증에 실패했습니다: row={source_row_number}"
                ) from error

    if actual_row_count != expected_row_count:
        raise DatasetLoadError(
            "CSV 행 수가 manifest와 일치하지 않습니다: "
            f"expected={expected_row_count}, actual={actual_row_count}"
        )


def iter_daily_ingestion_rows(
    csv_path: Path,
    manifest_path: Path,
    target_date: date,
) -> Iterator[tuple[Any, ...]]:
    """검증된 표준 CSV에서 지정 날짜의 PostgreSQL 적재 행만 반환한다."""
    for ingestion_row in iter_ingestion_rows(csv_path, manifest_path):
        if ingestion_row[SALE_DATE_INDEX] == target_date:
            yield ingestion_row


def load_csv_to_postgres(
    connection: psycopg.Connection[Any],
    csv_path: Path,
    manifest_path: Path,
    *,
    target_date: date | None = None,
) -> LoadResult:
    """전체 또는 지정 날짜의 신규 행만 COPY를 거쳐 raw 테이블에 삽입한다.

    같은 파일을 다시 처리하면 복합 기본키 충돌은 무시하고 신규 행만 반영한다.
    함수는 commit하지 않으므로 호출자가 전체 적재의 트랜잭션 경계를 결정한다.
    """
    input_rows = 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS retail_sales_stage
                (LIKE raw.retail_sales INCLUDING DEFAULTS)
                ON COMMIT DROP
            """
        )
        cursor.execute("TRUNCATE retail_sales_stage")

        copy_columns_sql = ", ".join(COPY_COLUMNS)
        with cursor.copy(
            f"COPY retail_sales_stage ({copy_columns_sql}) FROM STDIN"
        ) as copy:
            ingestion_rows = (
                iter_ingestion_rows(csv_path, manifest_path)
                if target_date is None
                else iter_daily_ingestion_rows(csv_path, manifest_path, target_date)
            )
            for ingestion_row in ingestion_rows:
                copy.write_row(ingestion_row)
                input_rows += 1

        cursor.execute(
            f"""
            INSERT INTO raw.retail_sales ({copy_columns_sql})
            SELECT {copy_columns_sql}
            FROM retail_sales_stage
            ON CONFLICT (source_file_sha256, source_row_number) DO NOTHING
            """
        )
        inserted_rows = cursor.rowcount

    return LoadResult(
        input_rows=input_rows,
        inserted_rows=inserted_rows,
        skipped_rows=input_rows - inserted_rows,
    )


def main() -> None:
    """환경변수의 PostgreSQL에 기본 표준 CSV를 적재한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="적재할 날짜(YYYY-MM-DD). 생략하면 전체 CSV를 적재한다.",
    )
    arguments = parser.parse_args()

    settings = DatabaseSettings.from_mapping(os.environ)
    connection_parameters = {
        "host": settings.host,
        "port": settings.port,
        "dbname": settings.database,
        "user": settings.user,
        "password": settings.password,
    }
    manifest = read_csv_manifest(arguments.manifest)

    # 감사 기록은 별도 autocommit 연결을 사용해 데이터 적재 롤백과 독립적으로 남긴다.
    with psycopg.connect(**connection_parameters, autocommit=True) as audit_connection:
        run_id = start_ingestion_run(
            audit_connection,
            manifest["target_sha256"],
            arguments.date,
        )
        try:
            with psycopg.connect(**connection_parameters) as data_connection:
                result = load_csv_to_postgres(
                    data_connection,
                    arguments.source,
                    arguments.manifest,
                    target_date=arguments.date,
                )
        except BaseException as error:
            fail_ingestion_run(audit_connection, run_id, error)
            raise
        succeed_ingestion_run(audit_connection, run_id, result)

    batch = arguments.date.isoformat() if arguments.date is not None else "all"
    print(
        f"적재 완료: run_id={run_id}, batch={batch}, input={result.input_rows}, "
        f"inserted={result.inserted_rows}, skipped={result.skipped_rows}"
    )


if __name__ == "__main__":
    main()
