"""지정한 날짜 범위의 일일 적재·검증 pipeline을 순서대로 실행한다."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.daily_pipeline import (
    DailyPipelineResult,
    run_daily_pipeline,
)
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


class BackfillDateRangeError(ValueError):
    """시작일과 종료일로 유효한 backfill 범위를 만들 수 없을 때의 예외."""


@dataclass(frozen=True)
class BackfillPipelineResult:
    """날짜 범위와 날짜별 pipeline 결과를 함께 전달한다."""

    start_date: date
    end_date: date
    daily_results: tuple[DailyPipelineResult, ...]


def run_backfill_pipeline(
    settings: DatabaseSettings,
    start_date: date,
    end_date: date,
    csv_path: Path,
    manifest_path: Path,
) -> BackfillPipelineResult:
    """시작일부터 종료일까지 일일 pipeline을 날짜순으로 실행한다.

    각 날짜는 기존 일일 pipeline의 독립된 트랜잭션과 감사 이력을 사용한다.
    한 날짜가 실패하면 예외를 그대로 전달하고 이후 날짜는 처리하지 않는다.
    """
    if start_date > end_date:
        raise BackfillDateRangeError(
            "backfill 시작일은 종료일보다 늦을 수 없습니다: "
            f"start={start_date}, end={end_date}"
        )

    daily_results = []
    target_date = start_date
    while target_date <= end_date:
        daily_results.append(
            run_daily_pipeline(
                settings,
                target_date,
                csv_path,
                manifest_path,
            )
        )
        target_date += timedelta(days=1)

    return BackfillPipelineResult(
        start_date=start_date,
        end_date=end_date,
        daily_results=tuple(daily_results),
    )


def main() -> None:
    """명령행에서 날짜 범위의 일일 pipeline을 연속 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        required=True,
        help="처리를 시작할 날짜(YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        required=True,
        help="처리를 끝낼 날짜(YYYY-MM-DD)",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    arguments = parser.parse_args()

    settings = DatabaseSettings.from_mapping(os.environ)
    result = run_backfill_pipeline(
        settings,
        arguments.start_date,
        arguments.end_date,
        arguments.source,
        arguments.manifest,
    )

    total_input_rows = sum(
        daily_result.ingestion.load_result.input_rows
        for daily_result in result.daily_results
    )
    total_inserted_rows = sum(
        daily_result.ingestion.load_result.inserted_rows
        for daily_result in result.daily_results
    )
    total_skipped_rows = sum(
        daily_result.ingestion.load_result.skipped_rows
        for daily_result in result.daily_results
    )
    print(
        "backfill pipeline 완료: "
        f"date_range={result.start_date}~{result.end_date}, "
        f"days={len(result.daily_results)}, input={total_input_rows}, "
        f"inserted={total_inserted_rows}, skipped={total_skipped_rows}"
    )


if __name__ == "__main__":
    main()
