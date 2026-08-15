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


def _display_value(value: object) -> str:
    """표의 빈 값을 구분하고 오류 메시지가 한 줄을 깨뜨리지 않게 정리한다."""
    if value is None:
        return "-"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return " ".join(str(value).split())


def format_ingestion_runs(records: tuple[IngestionRunRecord, ...]) -> str:
    """외부 표 라이브러리 없이 최근 실행 이력을 탭 구분 텍스트로 만든다."""
    columns = (
        "run_id",
        "batch_date",
        "status",
        "input",
        "inserted",
        "skipped",
        "started_at",
        "finished_at",
        "error",
    )
    lines = ["\t".join(columns)]
    for record in records:
        lines.append(
            "\t".join(
                _display_value(value)
                for value in (
                    record.run_id,
                    record.batch_date,
                    record.status,
                    record.input_rows,
                    record.inserted_rows,
                    record.skipped_rows,
                    record.started_at,
                    record.finished_at,
                    record.error_message,
                )
            )
        )
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
