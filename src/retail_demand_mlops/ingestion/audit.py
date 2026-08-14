"""PostgreSQL에 데이터 적재 실행의 시작과 결과를 기록한다."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import psycopg

if TYPE_CHECKING:
    from retail_demand_mlops.ingestion.loader import LoadResult


class IngestionAuditError(RuntimeError):
    """적재 실행 이력을 생성하거나 갱신하지 못했을 때의 예외."""


def start_ingestion_run(
    connection: psycopg.Connection[Any],
    source_checksum: str,
    batch_date: date | None,
) -> int:
    """running 상태의 실행 이력을 만들고 데이터베이스 run_id를 반환한다."""
    result = connection.execute(
        """
        INSERT INTO ops.ingestion_runs (source_file_sha256, batch_date, status)
        VALUES (%s, %s, 'running')
        RETURNING run_id
        """,
        (source_checksum, batch_date),
    ).fetchone()
    if result is None:
        raise IngestionAuditError("적재 실행 run_id를 생성하지 못했습니다")
    return int(result[0])


def succeed_ingestion_run(
    connection: psycopg.Connection[Any],
    run_id: int,
    load_result: LoadResult,
) -> None:
    """성공한 실행에 입력·삽입·중복 행 수와 종료 시각을 기록한다."""
    result = connection.execute(
        """
        UPDATE ops.ingestion_runs
        SET status = 'succeeded',
            input_rows = %s,
            inserted_rows = %s,
            skipped_rows = %s,
            finished_at = CURRENT_TIMESTAMP
        WHERE run_id = %s AND status = 'running'
        """,
        (
            load_result.input_rows,
            load_result.inserted_rows,
            load_result.skipped_rows,
            run_id,
        ),
    )
    if result.rowcount != 1:
        raise IngestionAuditError(f"성공 상태로 변경할 실행 이력이 없습니다: {run_id}")


def fail_ingestion_run(
    connection: psycopg.Connection[Any],
    run_id: int,
    error: BaseException,
) -> None:
    """실패 원인을 제한된 길이로 저장하고 실행을 종료 상태로 바꾼다."""
    error_message = f"{type(error).__name__}: {error}"[:2000]
    result = connection.execute(
        """
        UPDATE ops.ingestion_runs
        SET status = 'failed',
            error_message = %s,
            finished_at = CURRENT_TIMESTAMP
        WHERE run_id = %s AND status = 'running'
        """,
        (error_message, run_id),
    )
    if result.rowcount != 1:
        raise IngestionAuditError(f"실패 상태로 변경할 실행 이력이 없습니다: {run_id}")
