"""manifest와 PostgreSQL raw 적재 결과가 일치하는지 읽기 전용으로 검증한다."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.loader import (
    iter_daily_ingestion_rows,
    read_csv_manifest,
)
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


class LoadValidationError(RuntimeError):
    """manifest의 기대값과 PostgreSQL 적재 결과가 다를 때의 예외."""


@dataclass(frozen=True)
class LoadValidationReport:
    """검증 결과와 주요 품질 집계를 함께 전달하는 읽기 전용 보고서."""

    expected_rows: int
    actual_rows: int
    first_source_row: int | None
    last_source_row: int | None
    first_sale_date: date | None
    last_sale_date: date | None
    anonymous_rows: int
    cancellation_rows: int
    return_rows: int
    zero_price_rows: int
    negative_price_rows: int


@dataclass(frozen=True)
class DailyLoadValidationReport:
    """하루치 CSV 기대 범위와 PostgreSQL 실제 적재 결과를 비교한 보고서."""

    target_date: date
    expected_rows: int
    actual_rows: int
    first_source_row: int | None
    last_source_row: int | None
    anonymous_rows: int
    cancellation_rows: int
    return_rows: int


def validate_loaded_source(
    connection: psycopg.Connection[Any],
    manifest_path: Path,
) -> LoadValidationReport:
    """한 CSV 출처의 행 수·행 번호 범위와 데이터 품질 지표를 검증한다."""
    manifest = read_csv_manifest(manifest_path)
    source_checksum = manifest["target_sha256"]
    expected_rows = manifest["row_count"]

    result = connection.execute(
        """
        SELECT
            count(*),
            min(source_row_number),
            max(source_row_number),
            min(sale_date),
            max(sale_date),
            count(*) FILTER (WHERE customer_id IS NULL),
            count(*) FILTER (WHERE is_cancellation),
            count(*) FILTER (WHERE is_return),
            count(*) FILTER (WHERE is_zero_price),
            count(*) FILTER (WHERE is_negative_price)
        FROM raw.retail_sales
        WHERE source_file_sha256 = %s
        """,
        (source_checksum,),
    ).fetchone()
    if result is None:
        raise LoadValidationError("PostgreSQL 검증 집계를 가져오지 못했습니다")

    report = LoadValidationReport(
        expected_rows=expected_rows,
        actual_rows=int(result[0]),
        first_source_row=result[1],
        last_source_row=result[2],
        first_sale_date=result[3],
        last_sale_date=result[4],
        anonymous_rows=int(result[5]),
        cancellation_rows=int(result[6]),
        return_rows=int(result[7]),
        zero_price_rows=int(result[8]),
        negative_price_rows=int(result[9]),
    )

    mismatches = []
    if report.actual_rows != expected_rows:
        mismatches.append(
            f"행 수 expected={expected_rows}, actual={report.actual_rows}"
        )
    if expected_rows > 0 and report.first_source_row != 1:
        mismatches.append(f"첫 행 번호 expected=1, actual={report.first_source_row}")
    if expected_rows > 0 and report.last_source_row != expected_rows:
        mismatches.append(
            f"마지막 행 번호 expected={expected_rows}, actual={report.last_source_row}"
        )
    if expected_rows == 0 and (
        report.first_source_row is not None or report.last_source_row is not None
    ):
        mismatches.append("빈 입력인데 PostgreSQL에 출처 행 번호가 존재합니다")

    if mismatches:
        raise LoadValidationError("적재 검증 실패: " + "; ".join(mismatches))
    return report


def validate_loaded_date(
    connection: psycopg.Connection[Any],
    csv_path: Path,
    manifest_path: Path,
    target_date: date,
) -> DailyLoadValidationReport:
    """simulator의 하루치 기대 행과 PostgreSQL의 같은 날짜 적재를 비교한다."""
    expected_rows = 0
    expected_first_source_row = None
    expected_last_source_row = None
    for ingestion_row in iter_daily_ingestion_rows(
        csv_path,
        manifest_path,
        target_date,
    ):
        expected_rows += 1
        expected_first_source_row = expected_first_source_row or ingestion_row[1]
        expected_last_source_row = ingestion_row[1]

    manifest = read_csv_manifest(manifest_path)
    source_checksum = manifest["target_sha256"]

    result = connection.execute(
        """
        SELECT
            count(*),
            min(source_row_number),
            max(source_row_number),
            count(*) FILTER (WHERE customer_id IS NULL),
            count(*) FILTER (WHERE is_cancellation),
            count(*) FILTER (WHERE is_return)
        FROM raw.retail_sales
        WHERE source_file_sha256 = %s AND sale_date = %s
        """,
        (source_checksum, target_date),
    ).fetchone()
    if result is None:
        raise LoadValidationError("PostgreSQL 날짜별 검증 집계를 가져오지 못했습니다")

    report = DailyLoadValidationReport(
        target_date=target_date,
        expected_rows=expected_rows,
        actual_rows=int(result[0]),
        first_source_row=result[1],
        last_source_row=result[2],
        anonymous_rows=int(result[3]),
        cancellation_rows=int(result[4]),
        return_rows=int(result[5]),
    )

    mismatches = []
    if report.actual_rows != expected_rows:
        mismatches.append(
            f"행 수 expected={expected_rows}, actual={report.actual_rows}"
        )
    if report.first_source_row != expected_first_source_row:
        mismatches.append(
            "첫 행 번호 "
            f"expected={expected_first_source_row}, actual={report.first_source_row}"
        )
    if report.last_source_row != expected_last_source_row:
        mismatches.append(
            "마지막 행 번호 "
            f"expected={expected_last_source_row}, actual={report.last_source_row}"
        )
    if mismatches:
        raise LoadValidationError(
            f"{target_date.isoformat()} 날짜 배치 검증 실패: " + "; ".join(mismatches)
        )
    return report


def main() -> None:
    """환경변수의 PostgreSQL 전체 또는 날짜별 적재를 CSV 계약과 비교한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="검증할 날짜(YYYY-MM-DD). 생략하면 전체 적재를 검증한다.",
    )
    arguments = parser.parse_args()

    settings = DatabaseSettings.from_mapping(os.environ)
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password,
    ) as connection:
        if arguments.date is None:
            report = validate_loaded_source(connection, arguments.manifest)
        else:
            daily_report = validate_loaded_date(
                connection,
                arguments.source,
                arguments.manifest,
                arguments.date,
            )

    if arguments.date is None:
        print(
            "전체 적재 검증 완료: "
            f"rows={report.actual_rows}, "
            f"date_range={report.first_sale_date}~{report.last_sale_date}, "
            f"anonymous={report.anonymous_rows}, "
            f"cancellations={report.cancellation_rows}, "
            f"returns={report.return_rows}, "
            f"zero_price={report.zero_price_rows}, "
            f"negative_price={report.negative_price_rows}"
        )
    else:
        print(
            "날짜 배치 검증 완료: "
            f"date={daily_report.target_date}, rows={daily_report.actual_rows}, "
            f"source_rows={daily_report.first_source_row}~"
            f"{daily_report.last_source_row}, "
            f"anonymous={daily_report.anonymous_rows}, "
            f"cancellations={daily_report.cancellation_rows}, "
            f"returns={daily_report.return_rows}"
        )


if __name__ == "__main__":
    main()
