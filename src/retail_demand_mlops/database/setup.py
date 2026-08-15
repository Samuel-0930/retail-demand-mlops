"""번호가 붙은 SQL 파일을 순서대로 적용해 PostgreSQL 구조를 초기화한다."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import psycopg

from retail_demand_mlops.config import DatabaseSettings


DEFAULT_SQL_DIRECTORY = Path(__file__).resolve().parents[3] / "sql"


class DatabaseSetupError(RuntimeError):
    """적용할 SQL 파일을 찾거나 읽을 수 없을 때 발생하는 예외."""


def discover_sql_files(sql_directory: Path) -> tuple[Path, ...]:
    """세 자리 번호로 시작하는 SQL 파일을 이름순으로 찾아 반환한다."""
    if not sql_directory.is_dir():
        raise DatabaseSetupError(f"SQL 디렉터리가 없습니다: {sql_directory}")
    sql_files = tuple(sorted(sql_directory.glob("[0-9][0-9][0-9]_*.sql")))
    if not sql_files:
        raise DatabaseSetupError(f"적용할 SQL 파일이 없습니다: {sql_directory}")
    return sql_files


def apply_schema(
    connection: psycopg.Connection[Any],
    sql_directory: Path,
) -> tuple[str, ...]:
    """발견한 DDL을 한 연결의 현재 트랜잭션에서 순서대로 실행한다.

    함수는 commit하지 않는다. CLI의 연결 context가 모든 파일 성공 시 commit하고,
    예외가 발생하면 전체 DDL을 rollback해 부분 적용을 방지한다.
    """
    applied_files = []
    for sql_path in discover_sql_files(sql_directory):
        try:
            sql = sql_path.read_text(encoding="utf-8")
        except OSError as error:
            raise DatabaseSetupError(f"SQL 파일을 읽을 수 없습니다: {sql_path}") from error
        connection.execute(sql)
        applied_files.append(sql_path.name)
    return tuple(applied_files)


def main() -> None:
    """환경변수의 기존 PostgreSQL 데이터베이스에 프로젝트 구조를 적용한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sql-directory",
        type=Path,
        default=DEFAULT_SQL_DIRECTORY,
        help="번호가 붙은 SQL 파일이 있는 디렉터리",
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
        applied_files = apply_schema(connection, arguments.sql_directory)

    print(f"DB 스키마 초기화 완료: files={','.join(applied_files)}")


if __name__ == "__main__":
    main()
