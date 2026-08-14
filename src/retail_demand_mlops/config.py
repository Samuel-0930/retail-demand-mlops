"""환경변수에서 애플리케이션 설정을 읽고 유효성을 검증한다."""

from __future__ import annotations

from dataclasses import dataclass
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

