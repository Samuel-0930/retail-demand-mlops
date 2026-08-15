"""하루치 판매 데이터 적재와 검증을 순서대로 실행한다."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.loader import (
    IngestionRunResult,
    run_ingestion,
)
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)
from retail_demand_mlops.ingestion.validate import (
    DailyLoadValidationReport,
    validate_loaded_date,
)


@dataclass(frozen=True)
class DailyPipelineResult:
    """하루치 적재 결과와 후속 검증 결과를 함께 전달한다."""

    ingestion: IngestionRunResult
    validation: DailyLoadValidationReport


def run_daily_pipeline(
    settings: DatabaseSettings,
    target_date: date,
    csv_path: Path,
    manifest_path: Path,
) -> DailyPipelineResult:
    """지정 날짜를 적재한 뒤 같은 날짜의 PostgreSQL 결과를 검증한다."""
    ingestion_result = run_ingestion(
        settings,
        csv_path,
        manifest_path,
        target_date=target_date,
    )

    # 적재 commit이 끝난 뒤 새 연결에서 조회해 실제 저장 결과를 검증한다.
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password,
    ) as connection:
        validation_report = validate_loaded_date(
            connection,
            csv_path,
            manifest_path,
            target_date,
        )

    return DailyPipelineResult(
        ingestion=ingestion_result,
        validation=validation_report,
    )


def main() -> None:
    """명령행에서 하루치 적재와 검증을 한 번에 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        required=True,
        help="처리할 날짜(YYYY-MM-DD)",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    arguments = parser.parse_args()

    settings = DatabaseSettings.from_mapping(os.environ)
    result = run_daily_pipeline(
        settings,
        arguments.date,
        arguments.source,
        arguments.manifest,
    )
    print(
        "일일 pipeline 완료: "
        f"run_id={result.ingestion.run_id}, date={arguments.date}, "
        f"input={result.ingestion.load_result.input_rows}, "
        f"inserted={result.ingestion.load_result.inserted_rows}, "
        f"skipped={result.ingestion.load_result.skipped_rows}, "
        f"validated_rows={result.validation.actual_rows}"
    )


if __name__ == "__main__":
    main()
