"""수동 입력 날짜의 판매 데이터를 PostgreSQL에 적재하고 검증하는 Airflow DAG."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, get_current_context, task

from retail_demand_mlops.config import DatabaseSettings
from retail_demand_mlops.ingestion.daily_pipeline import run_daily_pipeline
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


DAG_ID = "retail_daily_ingestion"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def parse_target_date(raw_target_date: object) -> date:
    """Airflow Param 값을 모호하지 않은 ISO 날짜로 검증한다."""
    if not isinstance(raw_target_date, str):
        raise ValueError("target_date는 YYYY-MM-DD 문자열이어야 합니다")
    try:
        return date.fromisoformat(raw_target_date)
    except ValueError as error:
        raise ValueError(
            f"target_date가 올바른 날짜가 아닙니다: {raw_target_date!r}"
        ) from error


@dag(
    dag_id=DAG_ID,
    description="수동 날짜 한 건의 리테일 판매 적재와 검증",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 16, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    params={
        "target_date": Param(
            default="2009-12-01",
            type="string",
            format="date",
            description="처리할 원본 판매 날짜(YYYY-MM-DD)",
        )
    },
    tags=["retail-demand", "ingestion", "week-2"],
)
def build_retail_daily_ingestion_dag() -> None:
    """날짜 검증 뒤 기존 일일 pipeline을 호출하는 두 task DAG를 만든다."""

    @task(task_id="resolve_target_date")
    def resolve_target_date() -> str:
        """DAG 실행 시 전달된 날짜를 검증하고 표준 문자열로 반환한다."""
        context = get_current_context()
        target_date = parse_target_date(context["params"]["target_date"])
        return target_date.isoformat()

    @task(
        task_id="load_and_validate_daily_sales",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def load_and_validate_daily_sales(target_date_text: str) -> dict[str, int | str]:
        """기존 Python pipeline으로 하루치 적재와 검증을 수행한다."""
        target_date = parse_target_date(target_date_text)
        settings = DatabaseSettings.from_mapping(os.environ)

        # Airflow task의 작업 디렉터리가 달라도 같은 데이터 파일을 찾도록 절대경로를 쓴다.
        result = run_daily_pipeline(
            settings,
            target_date,
            PROJECT_ROOT / DEFAULT_CSV_PATH,
            PROJECT_ROOT / DEFAULT_MANIFEST_PATH,
        )
        summary = {
            "run_id": result.ingestion.run_id,
            "target_date": target_date.isoformat(),
            "input_rows": result.ingestion.load_result.input_rows,
            "inserted_rows": result.ingestion.load_result.inserted_rows,
            "skipped_rows": result.ingestion.load_result.skipped_rows,
            "validated_rows": result.validation.actual_rows,
        }
        LOGGER.info("Airflow 일일 pipeline 완료: %s", summary)
        return summary

    load_and_validate_daily_sales(resolve_target_date())


retail_daily_ingestion_dag = build_retail_daily_ingestion_dag()
