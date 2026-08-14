"""과거 CSV 데이터에서 하루치 판매 배치를 생성한다."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path


class SimulationDataError(ValueError):
    """원본 데이터로 정상적인 일별 배치를 만들 수 없을 때 발생하는 예외."""


def iter_daily_sales(
    source_path: Path,
    target_date: date,
    *,
    date_column: str = "date",
) -> Iterator[Mapping[str, str]]:
    """ISO 형식의 날짜가 ``target_date``와 일치하는 행을 순서대로 반환한다.

    CSV 전체를 메모리에 적재하지 않고 한 행씩 읽는다. 따라서 이후 더 큰
    데이터셋을 사용하더라도 시뮬레이터의 메모리 사용량이 급격히 늘지 않는다.
    """
    try:
        # newline=""은 csv 모듈이 플랫폼별 줄바꿈을 직접 처리하도록 해준다.
        source_file = source_path.open(encoding="utf-8", newline="")
    except FileNotFoundError as error:
        raise SimulationDataError(f"Source CSV does not exist: {source_path}") from error

    with source_file:
        reader = csv.DictReader(source_file)

        # 헤더가 없으면 각 값이 어떤 필드인지 판단할 수 없으므로 즉시 중단한다.
        if reader.fieldnames is None:
            raise SimulationDataError("Source CSV must include a header row")

        # 데이터셋마다 날짜 컬럼명이 다를 수 있어 date_column 인자로 지정한다.
        if date_column not in reader.fieldnames:
            raise SimulationDataError(
                f"Source CSV is missing the date column: {date_column}"
            )

        # 첫 번째 데이터 행은 CSV의 두 번째 줄이므로 행 번호를 2부터 센다.
        for row_number, row in enumerate(reader, start=2):
            raw_date = row.get(date_column, "")
            try:
                # 현재 입력 계약은 YYYY-MM-DD 형식이며, 잘못된 날짜를 조용히 건너뛰지 않는다.
                row_date = date.fromisoformat(raw_date)
            except ValueError as error:
                raise SimulationDataError(
                    f"Invalid ISO date at CSV row {row_number}: {raw_date!r}"
                ) from error

            # 생성기이므로 요청한 날짜의 행만 호출자에게 즉시 전달한다.
            if row_date == target_date:
                yield row
