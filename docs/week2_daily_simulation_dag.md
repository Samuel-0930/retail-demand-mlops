# Week 2 자동 일일 시뮬레이션 DAG

`retail_daily_simulation` DAG는 현재 Airflow의 하루 구간을 UCI 과거 판매 날짜로
변환한 뒤 기존 일일 pipeline을 호출합니다. 수동 복구 DAG와 역할을 분리했으며,
처음 등록될 때는 pause 상태이므로 자동 적재가 바로 시작되지 않습니다.

## 환경 설정

`.env`에 다음 값을 추가합니다.

```dotenv
RETAIL_SIMULATION_SCHEDULE_START_DATE=2026-08-16
RETAIL_SIMULATION_SOURCE_START_DATE=2009-12-01
RETAIL_SIMULATION_SOURCE_END_DATE=2011-12-09
```

- schedule 시작일: 현재 달력에서 시뮬레이션을 시작할 날짜
- source 시작일: 첫 번째로 재생할 과거 판매 날짜
- source 종료일: 마지막으로 재생할 과거 판매 날짜

세 값 중 하나라도 없거나 날짜 형식이 잘못되면 Airflow가 DAG를 등록하지 않습니다.
현재 날짜를 임의로 추측해 잘못된 빈 배치를 성공 처리하지 않기 위한 제한입니다.

## 날짜 연결

현재 설정에서는 다음과 같이 연결됩니다.

| Airflow 하루 구간 | 실행 시점 | 처리 판매 날짜 |
|---|---|---|
| 2026-08-16 | 2026-08-17 00:00 이후 | 2009-12-01 |
| 2026-08-17 | 2026-08-18 00:00 이후 | 2009-12-02 |
| 2026-08-18 | 2026-08-19 00:00 이후 | 2009-12-03 |

마지막 판매 날짜 `2011-12-09`는 Airflow 구간 시작일 `2028-08-23`에 연결됩니다.
DAG의 종료일도 이 날짜로 계산되므로 원본 기간을 넘는 빈 실행을 만들지 않습니다.

## 안전한 등록 확인

소스 코드가 바뀌었으므로 Airflow 전용 환경에 프로젝트를 다시 설치한 뒤 확인합니다.

```bash
.airflow-venv/bin/python -m pip install .
source scripts/airflow_env.sh
.airflow-venv/bin/airflow dags reserialize
.airflow-venv/bin/airflow dags list --output plain
```

목록에서 `retail_daily_simulation`의 `is_paused`가 `True`여야 합니다. 현재 검증에서는
세 DAG 모두 import 오류 없이 등록됐고 자동 DAG가 pause 상태인 것을 확인했습니다.

## 아직 실행하지 않는 것

- DAG unpause
- scheduler 상시 실행
- 자동 일일 PostgreSQL 적재

이번 단계는 schedule과 날짜 매핑이 안전한지 확인한 단계입니다. 다음 단계에서
운영 Runbook을 정리하면서 unpause 전에 확인할 체크리스트와 실행 방법을 결정합니다.
