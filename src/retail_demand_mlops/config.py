"""환경변수에서 애플리케이션 설정을 읽고 유효성을 검증한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping


class ConfigurationError(ValueError):
    """필수 설정이 없거나 올바른 형식이 아닐 때 발생하는 예외."""


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL 연결에 필요한 값만 비즈니스 로직과 분리해 보관한다."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_mapping(cls, environment: Mapping[str, str]) -> DatabaseSettings:
        """환경변수 매핑을 검증하고 변경할 수 없는 설정 객체를 만든다."""
        host = environment.get("RETAIL_DB_HOST", "localhost").strip()
        raw_port = environment.get("RETAIL_DB_PORT", "5432").strip()
        database = environment.get("RETAIL_DB_NAME", "").strip()
        user = environment.get("RETAIL_DB_USER", "").strip()
        password = environment.get("RETAIL_DB_PASSWORD", "")

        if not host:
            raise ConfigurationError("RETAIL_DB_HOST가 비어 있습니다")
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ConfigurationError("RETAIL_DB_PORT는 정수여야 합니다") from error
        if not 1 <= port <= 65535:
            raise ConfigurationError("RETAIL_DB_PORT는 1~65535 범위여야 합니다")
        if not database:
            raise ConfigurationError("RETAIL_DB_NAME이 필요합니다")
        if not user:
            raise ConfigurationError("RETAIL_DB_USER가 필요합니다")

        return cls(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )


@dataclass(frozen=True)
class SimulationSettings:
    """현재 Airflow 일정과 과거 판매 기간을 연결하는 기준 날짜 설정."""

    schedule_start_date: date
    source_start_date: date
    source_end_date: date

    @classmethod
    def from_mapping(cls, environment: Mapping[str, str]) -> SimulationSettings:
        """필수 ISO 날짜 환경변수를 읽고 유효한 시뮬레이션 범위를 만든다."""
        schedule_start_date = _read_required_date(
            environment,
            "RETAIL_SIMULATION_SCHEDULE_START_DATE",
        )
        source_start_date = _read_required_date(
            environment,
            "RETAIL_SIMULATION_SOURCE_START_DATE",
        )
        source_end_date = _read_required_date(
            environment,
            "RETAIL_SIMULATION_SOURCE_END_DATE",
        )
        if source_start_date > source_end_date:
            raise ConfigurationError(
                "시뮬레이션 원본 시작일은 종료일보다 늦을 수 없습니다"
            )

        return cls(
            schedule_start_date=schedule_start_date,
            source_start_date=source_start_date,
            source_end_date=source_end_date,
        )

    @property
    def schedule_end_date(self) -> date:
        """원본 마지막 날짜와 연결되는 마지막 schedule interval 시작일을 반환한다."""
        source_day_count = (self.source_end_date - self.source_start_date).days
        return self.schedule_start_date + timedelta(days=source_day_count)


def _read_required_date(environment: Mapping[str, str], key: str) -> date:
    """환경변수 하나를 필수 ISO 날짜로 검증한다."""
    raw_date = environment.get(key, "").strip()
    if not raw_date:
        raise ConfigurationError(f"{key}가 필요합니다")
    try:
        return date.fromisoformat(raw_date)
    except ValueError as error:
        raise ConfigurationError(f"{key}는 YYYY-MM-DD 형식이어야 합니다") from error
