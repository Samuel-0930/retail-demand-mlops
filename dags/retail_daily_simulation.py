"""현재 일일 data interval을 과거 판매 날짜로 변환해 처리하는 Airflow DAG."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable

from retail_demand_mlops.config import DatabaseSettings, SimulationSettings
from retail_demand_mlops.ingestion.daily_pipeline import run_daily_pipeline
from retail_demand_mlops.ingestion.simulator import map_simulation_target_date
from retail_demand_mlops.ingestion.transform import (
    DEFAULT_CSV_PATH,
    DEFAULT_MANIFEST_PATH,
)


DAG_ID = "retail_daily_simulation"
TIMEZONE_NAME = "Asia/Seoul"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)

# schedule 경계는 DAG를 읽을 때 필요하므로 환경변수 전용 설정 객체로 먼저 검증한다.
SIMULATION_SETTINGS = SimulationSettings.from_mapping(os.environ)


def _as_schedule_datetime(target_date: date) -> pendulum.DateTime:
    """설정의 날짜를 서울 자정 기준 Airflow datetime으로 변환한다."""
    return pendulum.datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tz=TIMEZONE_NAME,
    )


def resolve_simulation_target_date(data_interval_start: object) -> str:
    """Airflow data interval 시작일을 과거 원본 판매 날짜 문자열로 변환한다."""
    if not isinstance(data_interval_start, datetime):
        raise ValueError("자동 일일 DAG에는 data_interval_start가 필요합니다")

    interval_start_date = data_interval_start.astimezone(
        pendulum.timezone(TIMEZONE_NAME)
    ).date()
    target_date = map_simulation_target_date(
        interval_start_date=interval_start_date,
        schedule_start_date=SIMULATION_SETTINGS.schedule_start_date,
        source_start_date=SIMULATION_SETTINGS.source_start_date,
        source_end_date=SIMULATION_SETTINGS.source_end_date,
    )
    return target_date.isoformat()


@dag(
    dag_id=DAG_ID,
    description="현재 일일 구간을 UCI 과거 판매 날짜로 순차 재생",
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone=TIMEZONE_NAME),
    start_date=_as_schedule_datetime(SIMULATION_SETTINGS.schedule_start_date),
    end_date=_as_schedule_datetime(SIMULATION_SETTINGS.schedule_end_date),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=["retail-demand", "ingestion", "simulation", "scheduled", "week-2"],
)
def build_retail_daily_simulation_dag() -> None:
    """일정 날짜를 원본 날짜로 매핑한 뒤 기존 일일 pipeline을 호출한다."""

    @task(task_id="resolve_simulation_target_date")
    def resolve_target_date() -> str:
        """현재 scheduled run의 완료된 하루 구간을 원본 판매 날짜로 변환한다."""
        context = get_current_context()
        return resolve_simulation_target_date(context.get("data_interval_start"))

    @task(
        task_id="load_simulated_daily_sales",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def load_simulated_daily_sales(target_date_text: str) -> dict[str, int | str]:
        """매핑된 과거 날짜를 기존 Python 일일 pipeline으로 처리한다."""
        target_date = datetime.strptime(target_date_text, "%Y-%m-%d").date()
        database_settings = DatabaseSettings.from_mapping(os.environ)

        # scheduler의 작업 디렉터리와 관계없이 같은 CSV와 manifest를 사용한다.
        result = run_daily_pipeline(
            database_settings,
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
        LOGGER.info("Airflow 일일 시뮬레이션 완료: %s", summary)
        return summary

    load_simulated_daily_sales(resolve_target_date())


retail_daily_simulation_dag = build_retail_daily_simulation_dag()
