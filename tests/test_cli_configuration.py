from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class CliConfigurationTest(unittest.TestCase):
    """사용자용 CLI 이름이 의도한 실행 함수에 연결되는지 확인한다."""

    def test_project_scripts_point_to_existing_main_functions(self) -> None:
        """설치 시 생성되는 바로가기가 기존 비즈니스 로직을 그대로 호출해야 한다."""
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as pyproject_file:
            configuration = tomllib.load(pyproject_file)

        expected_scripts = {
            "retail-download": "retail_demand_mlops.ingestion.download:main",
            "retail-profile": "retail_demand_mlops.ingestion.profile:main",
            "retail-transform": "retail_demand_mlops.ingestion.transform:main",
            "retail-db-setup": "retail_demand_mlops.database.setup:main",
            "retail-load": "retail_demand_mlops.ingestion.loader:main",
            "retail-validate": "retail_demand_mlops.ingestion.validate:main",
            "retail-daily": "retail_demand_mlops.ingestion.daily_pipeline:main",
            "retail-backfill": (
                "retail_demand_mlops.ingestion.backfill_pipeline:main"
            ),
            "retail-runs": "retail_demand_mlops.ingestion.status:main",
        }

        self.assertEqual(configuration["project"]["scripts"], expected_scripts)


if __name__ == "__main__":
    unittest.main()
