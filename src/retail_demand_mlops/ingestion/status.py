"""PostgreSQL의 최근 적재 실행 이력을 읽기 전용으로 조회한다."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import psycopg

from retail_demand_mlops.config import DatabaseSettings


INGESTION_STATUSES = ("running", "succeeded", "failed")


class IngestionStatusQueryError(ValueError):
    """안전한 범위로 적재 실행 이력을 조회할 수 없을 때의 예외."""


@dataclass(frozen=True)
class IngestionRunRecord:
    """운영자가 확인할 한 번의 적재 실행 결과를 나타낸다."""

    run_id: int
    batch_date: date | None
    status: str
    input_rows: int | None
    inserted_rows: int | None
    skipped_rows: int | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


def list_recent_ingestion_runs(
    connection: psycopg.Connection[Any],
    limit: int = 10,
    *,
    status: str | None = None,
    batch_date: date | None = None,
) -> tuple[IngestionRunRecord, ...]:
    """선택한 상태·날짜의 최근 적재 실행을 조회하며 데이터는 변경하지 않는다."""
    if not 1 <= limit <= 100:
        raise IngestionStatusQueryError("조회 개수는 1~100 범위여야 합니다")
    if status is not None and status not in INGESTION_STATUSES:
        raise IngestionStatusQueryError(f"지원하지 않는 실행 상태입니다: {status}")

    filters = []
    parameters: list[object] = []
    if status is not None:
        filters.append("status = %s")
        parameters.append(status)
    if batch_date is not None:
        filters.append("batch_date = %s")
        parameters.append(batch_date)

    # SQL 구조에는 코드가 정한 조건만 넣고 사용자 값은 별도 파라미터로 전달한다.
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    parameters.append(limit)

    rows = connection.execute(
        f"""
        SELECT
            run_id,
            batch_date,
            status,
            input_rows,
            inserted_rows,
            skipped_rows,
            error_message,
            started_at,
            finished_at
        FROM ops.ingestion_runs
        {where_clause}
        ORDER BY run_id DESC
        LIMIT %s
        """,
        tuple(parameters),
    ).fetchall()

    return tuple(
        IngestionRunRecord(
            run_id=int(row[0]),
            batch_date=row[1],
            status=str(row[2]),
            input_rows=row[3],
            inserted_rows=row[4],
            skipped_rows=row[5],
            error_message=row[6],
            started_at=row[7],
            finished_at=row[8],
        )
        for row in rows
    )


def _display_count(value: int | None) -> str:
    """행 수의 빈 값을 구분하고 큰 숫자에는 천 단위 구분자를 넣는다."""
    if value is None:
        return "-"
    return f"{value:,}"


def _display_duration(record: IngestionRunRecord) -> str:
    """완료된 실행 시간을 초로 표시하고 진행 중이면 빈 값으로 구분한다."""
    if record.finished_at is None:
        return "-"
    return f"{(record.finished_at - record.started_at).total_seconds():.2f}"


def _display_error(error_message: str, max_length: int = 55) -> str:
    """오류를 한 줄로 정리하고 터미널 폭을 넘지 않도록 제한한다."""
    single_line_error = " ".join(error_message.split())
    if len(single_line_error) <= max_length:
        return single_line_error
    return f"{single_line_error[: max_length - 1]}…"


def format_ingestion_runs(records: tuple[IngestionRunRecord, ...]) -> str:
    """최근 실행의 핵심 정보만 일반 터미널 폭에 맞춘 표로 만든다."""
    lines = [
        f"{'RUN':>4}  {'BATCH_DATE':<10}  {'STATUS':<9}  "
        f"{'INPUT':>9}  {'INSERTED':>9}  {'SKIPPED':>9}  {'SECONDS':>7}"
    ]
    for record in records:
        batch_date = record.batch_date.isoformat() if record.batch_date else "-"
        lines.append(
            f"{record.run_id:>4}  {batch_date:<10}  {record.status:<9}  "
            f"{_display_count(record.input_rows):>9}  "
            f"{_display_count(record.inserted_rows):>9}  "
            f"{_display_count(record.skipped_rows):>9}  "
            f"{_display_duration(record):>7}"
        )
        if record.error_message is not None:
            lines.append(f"      error: {_display_error(record.error_message)}")
    return "\n".join(lines)


def main() -> None:
    """명령행에서 최근 PostgreSQL 적재 실행 이력을 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="가져올 최근 실행 개수(기본 10, 최대 100)",
    )
    parser.add_argument(
        "--status",
        choices=INGESTION_STATUSES,
        help="running, succeeded, failed 중 조회할 실행 상태",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="조회할 배치 날짜(YYYY-MM-DD)",
    )
    arguments = parser.parse_args()

    settings = DatabaseSettings.from_mapping(os.environ)
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password,
        options="-c default_transaction_read_only=on",
    ) as connection:
        records = list_recent_ingestion_runs(
            connection,
            arguments.limit,
            status=arguments.status,
            batch_date=arguments.date,
        )

    print(format_ingestion_runs(records))


if __name__ == "__main__":
    main()
