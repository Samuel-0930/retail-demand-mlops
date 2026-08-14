"""UCI Online Retail II 원본 데이터를 안전하게 내려받는다."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


DATASET_ARCHIVE_URL = (
    "https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip"
)
DATASET_MEMBER_NAME = "online_retail_II.xlsx"
DEFAULT_TARGET_PATH = Path("data/raw/online_retail_II.xlsx")


class DatasetDownloadError(RuntimeError):
    """원본 데이터를 완전하고 신뢰할 수 있는 상태로 저장하지 못한 경우의 예외."""


def calculate_sha256(path: Path) -> str:
    """큰 파일도 메모리에 한꺼번에 올리지 않고 SHA-256을 계산한다."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(
    archive_url: str,
    target_path: Path,
    *,
    member_name: str = DATASET_MEMBER_NAME,
) -> bool:
    """ZIP에서 원본 XLSX를 추출하고, 새로 저장했는지 여부를 반환한다.

    대상 파일과 체크섬 파일이 이미 일치하면 네트워크 요청 없이 종료한다.
    다운로드와 추출은 임시 디렉터리에서 끝낸 뒤 원자적으로 이동하므로,
    실행이 중단되어도 불완전한 원본 파일이 최종 경로에 남지 않는다.
    """
    checksum_path = target_path.with_suffix(f"{target_path.suffix}.sha256")
    if target_path.exists():
        if not checksum_path.exists():
            raise DatasetDownloadError(
                f"기존 원본의 체크섬 파일이 없습니다: {checksum_path}"
            )

        expected_checksum = checksum_path.read_text(encoding="utf-8").strip()
        if calculate_sha256(target_path) != expected_checksum:
            raise DatasetDownloadError(f"기존 원본의 체크섬이 일치하지 않습니다: {target_path}")
        return False

    target_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=target_path.parent) as temporary_directory:
        temporary_path = Path(temporary_directory)
        archive_path = temporary_path / "dataset.zip"
        extracted_path = temporary_path / member_name

        try:
            request = urllib.request.Request(
                archive_url,
                headers={"User-Agent": "retail-demand-mlops/0.1"},
            )
            with urllib.request.urlopen(request) as response, archive_path.open(
                "wb"
            ) as archive_file:
                shutil.copyfileobj(response, archive_file)

            with zipfile.ZipFile(archive_path) as archive:
                if member_name not in archive.namelist():
                    raise DatasetDownloadError(
                        f"ZIP에 필요한 파일이 없습니다: {member_name}"
                    )
                with archive.open(member_name) as source_file, extracted_path.open(
                    "wb"
                ) as target_file:
                    shutil.copyfileobj(source_file, target_file)
        except (OSError, zipfile.BadZipFile) as error:
            raise DatasetDownloadError(f"원본 데이터 다운로드에 실패했습니다: {error}") from error

        checksum = calculate_sha256(extracted_path)
        extracted_path.replace(target_path)

        temporary_checksum_path = temporary_path / checksum_path.name
        temporary_checksum_path.write_text(f"{checksum}\n", encoding="utf-8")
        temporary_checksum_path.replace(checksum_path)

    return True


def main() -> None:
    """명령행에서 공식 UCI 원본 데이터를 기본 경로에 내려받는다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET_PATH,
        help="추출한 XLSX를 저장할 경로",
    )
    arguments = parser.parse_args()

    created = download_dataset(DATASET_ARCHIVE_URL, arguments.target)
    status = "다운로드 완료" if created else "기존 파일 검증 완료"
    print(f"{status}: {arguments.target}")


if __name__ == "__main__":
    main()
