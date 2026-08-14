from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from retail_demand_mlops.ingestion.download import (
    DatasetDownloadError,
    calculate_sha256,
    download_dataset,
)


class DownloadDatasetTest(unittest.TestCase):
    """원본 다운로드의 정상 저장, 재실행, 무결성 검증을 확인한다."""

    def setUp(self) -> None:
        # 외부 네트워크와 무관하게 테스트하도록 로컬 ZIP을 원본처럼 사용한다.
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root_path = Path(self.temporary_directory.name)
        self.archive_path = self.root_path / "source.zip"
        self.target_path = self.root_path / "raw" / "dataset.xlsx"
        self.member_name = "dataset.xlsx"

        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr(self.member_name, b"xlsx-content")

    def test_downloads_member_and_writes_matching_checksum(self) -> None:
        """ZIP 내부 원본과 그 무결성을 확인할 체크섬을 함께 저장해야 한다."""
        created = download_dataset(
            self.archive_path.as_uri(),
            self.target_path,
            member_name=self.member_name,
        )

        checksum_path = self.target_path.with_suffix(".xlsx.sha256")
        self.assertTrue(created)
        self.assertEqual(self.target_path.read_bytes(), b"xlsx-content")
        self.assertEqual(
            checksum_path.read_text(encoding="utf-8").strip(),
            calculate_sha256(self.target_path),
        )

    def test_skips_download_when_existing_checksum_matches(self) -> None:
        """검증된 원본이 있으면 네트워크에 다시 접근하지 않아야 한다."""
        download_dataset(
            self.archive_path.as_uri(),
            self.target_path,
            member_name=self.member_name,
        )
        self.archive_path.unlink()

        created = download_dataset(
            self.archive_path.as_uri(),
            self.target_path,
            member_name=self.member_name,
        )

        self.assertFalse(created)

    def test_rejects_existing_file_with_mismatched_checksum(self) -> None:
        """손상되었거나 변경된 원본을 정상 파일로 오인하지 않아야 한다."""
        download_dataset(
            self.archive_path.as_uri(),
            self.target_path,
            member_name=self.member_name,
        )
        self.target_path.write_bytes(b"corrupted")

        with self.assertRaisesRegex(DatasetDownloadError, "체크섬이 일치하지 않습니다"):
            download_dataset(
                self.archive_path.as_uri(),
                self.target_path,
                member_name=self.member_name,
            )


if __name__ == "__main__":
    unittest.main()
