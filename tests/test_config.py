from __future__ import annotations

import unittest

from retail_demand_mlops.config import ConfigurationError, DatabaseSettings


class DatabaseSettingsTest(unittest.TestCase):
    """데이터베이스 설정의 기본값과 필수값 검증을 확인한다."""

    def test_reads_required_values_with_connection_defaults(self) -> None:
        """호스트와 포트를 생략하면 안전한 로컬 기본값을 사용해야 한다."""
        settings = DatabaseSettings.from_mapping(
            {
                "RETAIL_DB_NAME": "retail_demand",
                "RETAIL_DB_USER": "retail_app",
                "RETAIL_DB_PASSWORD": "secret",
            }
        )

        self.assertEqual(settings.host, "localhost")
        self.assertEqual(settings.port, 5432)
        self.assertEqual(settings.database, "retail_demand")
        self.assertEqual(settings.password, "secret")

    def test_allows_empty_password_for_local_trust_authentication(self) -> None:
        """로컬 개발 환경의 소켓 인증은 비밀번호 없이 사용할 수 있어야 한다."""
        settings = DatabaseSettings.from_mapping(
            {
                "RETAIL_DB_NAME": "retail_demand",
                "RETAIL_DB_USER": "retail_app",
            }
        )

        self.assertEqual(settings.password, "")

    def test_rejects_missing_database_name(self) -> None:
        """적재 대상이 불명확하면 기본 데이터베이스에 실수로 연결하지 않아야 한다."""
        with self.assertRaisesRegex(ConfigurationError, "RETAIL_DB_NAME이 필요합니다"):
            DatabaseSettings.from_mapping({"RETAIL_DB_USER": "retail_app"})

    def test_rejects_invalid_port(self) -> None:
        """연결 시도 전에 잘못된 포트 형식을 명확하게 알려야 한다."""
        with self.assertRaisesRegex(ConfigurationError, "정수여야 합니다"):
            DatabaseSettings.from_mapping(
                {
                    "RETAIL_DB_PORT": "postgres",
                    "RETAIL_DB_NAME": "retail_demand",
                    "RETAIL_DB_USER": "retail_app",
                }
            )


if __name__ == "__main__":
    unittest.main()
