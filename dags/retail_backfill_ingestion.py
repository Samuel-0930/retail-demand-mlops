"""최대 3일의 판매 데이터를 날짜순으로 적재하고 검증하는 Airflow DAG."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, get_current_context, task

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.backfill_pipeline import run_backfill_pipeline
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


DAG_ID = "retail_backfill_ingestion"
MAX_BACKFILL_DAYS = 3
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def _parse_date_parameter(raw_date: object, parameter_name: str) -> date:
    """Airflow Param 하나를 모호하지 않은 ISO 날짜로 변환한다."""
    if not isinstance(raw_date, str):
        raise ValueError(f"{parameter_name}는 YYYY-MM-DD 문자열이어야 합니다")
    try:
        return date.fromisoformat(raw_date)
    except ValueError as error:
        raise ValueError(
            f"{parameter_name}가 올바른 날짜가 아닙니다: {raw_date!r}"
        ) from error


def parse_backfill_date_range(
    raw_start_date: object,
    raw_end_date: object,
) -> tuple[date, date]:
    """시작일과 종료일을 포함하는 최대 3일 backfill 범위를 검증한다."""
    start_date = _parse_date_parameter(raw_start_date, "start_date")
    end_date = _parse_date_parameter(raw_end_date, "end_date")

    if start_date > end_date:
        raise ValueError("backfill 시작일은 종료일보다 늦을 수 없습니다")

    day_count = (end_date - start_date).days + 1
    if day_count > MAX_BACKFILL_DAYS:
        raise ValueError(
            f"backfill은 한 번에 최대 {MAX_BACKFILL_DAYS}일만 실행할 수 있습니다: "
            f"requested_days={day_count}"
        )

    return start_date, end_date


@dag(
    dag_id=DAG_ID,
    description="최대 3일의 리테일 판매 데이터를 날짜순으로 적재하고 검증",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 16, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    params={
        "start_date": Param(
            default="2009-12-01",
            type="string",
            format="date",
            description="처리를 시작할 원본 판매 날짜(YYYY-MM-DD)",
        ),
        "end_date": Param(
            default="2009-12-03",
            type="string",
            format="date",
            description="처리를 끝낼 원본 판매 날짜(YYYY-MM-DD, 최대 3일)",
        ),
    },
    tags=["retail-demand", "ingestion", "backfill", "week-2"],
)
def build_retail_backfill_ingestion_dag() -> None:
    """범위를 검증한 뒤 기존 순차 backfill pipeline을 호출하는 DAG를 만든다."""

    @task(task_id="resolve_backfill_date_range")
    def resolve_backfill_date_range() -> dict[str, str]:
        """DAG 실행 시 입력된 범위를 검증하고 표준 날짜 문자열로 반환한다."""
        context = get_current_context()
        start_date, end_date = parse_backfill_date_range(
            context["params"]["start_date"],
            context["params"]["end_date"],
        )
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

    @task(
        task_id="run_sequential_backfill",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def run_sequential_backfill(date_range: dict[str, str]) -> dict[str, object]:
        """기존 Python pipeline으로 검증된 날짜 범위를 순서대로 처리한다."""
        start_date, end_date = parse_backfill_date_range(
            date_range["start_date"],
            date_range["end_date"],
        )
        settings = DatabaseSettings.from_mapping(os.environ)

        # Airflow 실행 위치와 관계없이 프로젝트의 표준 CSV와 manifest를 사용한다.
        result = run_backfill_pipeline(
            settings,
            start_date,
            end_date,
            PROJECT_ROOT / DEFAULT_CSV_PATH,
            PROJECT_ROOT / DEFAULT_MANIFEST_PATH,
        )
        daily_results = result.daily_results
        summary = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": len(daily_results),
            "run_ids": [daily_result.ingestion.run_id for daily_result in daily_results],
            "input_rows": sum(
                daily_result.ingestion.load_result.input_rows
                for daily_result in daily_results
            ),
            "inserted_rows": sum(
                daily_result.ingestion.load_result.inserted_rows
                for daily_result in daily_results
            ),
            "skipped_rows": sum(
                daily_result.ingestion.load_result.skipped_rows
                for daily_result in daily_results
            ),
            "validated_rows": sum(
                daily_result.validation.actual_rows for daily_result in daily_results
            ),
        }
        LOGGER.info("Airflow 순차 backfill 완료: %s", summary)
        return summary

    run_sequential_backfill(resolve_backfill_date_range())


retail_backfill_ingestion_dag = build_retail_backfill_ingestion_dag()

