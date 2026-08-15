"""과거 CSV 데이터에서 하루치 판매 배치를 생성한다."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Generator


class SimulationDataError(ValueError):
    """원본 데이터로 정상적인 일별 배치를 만들 수 없을 때 발생하는 예외."""


@dataclass(frozen=True)
class SimulatedSale:
    """원본 데이터 행 번호와 날짜별 판매 값을 함께 보존한다."""

    source_row_number: int
    values: Mapping[str, str]


def iter_daily_sales_records(
    source_path: Path,
    target_date: date,
    *,
    date_column: str = "date",
) -> Generator[SimulatedSale, None, int]:
    """지정 날짜의 행 번호와 값을 반환하고 전체 데이터 행 수로 종료한다.

    행 번호는 헤더를 제외한 첫 데이터 행을 1로 센다. generator의 종료값은
    CSV 전체 데이터 행 수이며 loader가 manifest와 완전성을 비교할 때 사용한다.
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

        row_count = 0
        for source_row_number, row in enumerate(reader, start=1):
            row_count = source_row_number
            raw_date = row.get(date_column) or ""
            try:
                # 현재 입력 계약은 YYYY-MM-DD 형식이며, 잘못된 날짜를 조용히 건너뛰지 않는다.
                row_date = date.fromisoformat(raw_date)
            except ValueError as error:
                csv_row_number = source_row_number + 1
                raise SimulationDataError(
                    f"Invalid ISO date at CSV row {csv_row_number}: {raw_date!r}"
                ) from error

            if row_date == target_date:
                yield SimulatedSale(
                    source_row_number=source_row_number,
                    values=row,
                )

    return row_count


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
    for simulated_sale in iter_daily_sales_records(
        source_path,
        target_date,
        date_column=date_column,
    ):
        # 기존 호출자는 행 번호 없이 값만 받도록 공개 인터페이스를 유지한다.
        yield simulated_sale.values
