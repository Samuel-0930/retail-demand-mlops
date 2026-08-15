# Week 2 소규모 backfill DAG

`retail_backfill_ingestion` DAG는 시작일과 종료일을 입력받아 최대 3일의 판매 데이터를
날짜순으로 적재하고 검증합니다. 자동 일정은 없으며 한 번에 하나의 DAG run만
실행할 수 있습니다.

## 작업 순서

1. `resolve_backfill_date_range`: 날짜 형식, 날짜 순서, 최대 3일 제한 확인
2. `run_sequential_backfill`: 기존 `run_backfill_pipeline()`으로 하루씩 순서대로 처리

두 번째 task 안에서는 각 날짜마다 기존 일일 pipeline이 실행됩니다. 따라서
PostgreSQL의 `ops.ingestion_runs`에는 날짜별 실행 이력이 각각 한 줄씩 남습니다.

## 수동 실행

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
source scripts/airflow_env.sh
.airflow-venv/bin/airflow dags test retail_backfill_ingestion \
  --conf '{"start_date":"2009-12-01","end_date":"2009-12-03"}'
```

4일 이상을 입력하거나 시작일이 종료일보다 늦으면 PostgreSQL 적재 전에 실패합니다.
이 제한은 실수로 전체 과거 데이터를 한꺼번에 다시 처리하지 못하게 하는 안전장치입니다.

## 확인된 결과

2026-08-16에 `2009-12-01`부터 `2009-12-03`까지 실행한 결과입니다.

| 적재 run ID | 날짜 | 입력 | 삽입 | 건너뜀 | 상태 |
|---:|---|---:|---:|---:|---|
| 11 | 2009-12-01 | 3,223 | 0 | 3,223 | `succeeded` |
| 12 | 2009-12-02 | 3,277 | 0 | 3,277 | `succeeded` |
| 13 | 2009-12-03 | 3,002 | 0 | 3,002 | `succeeded` |
| 합계 | 3일 | 9,502 | 0 | 9,502 | `success` |

세 날짜가 run ID 11, 12, 13 순서로 처리됐습니다. 데이터는 이미 적재돼 있었으므로
9,502행을 모두 건너뛰었고, PostgreSQL의 날짜별 최종 행 수도 실행 전과 같았습니다.
즉, 여러 날짜를 Airflow로 묶어 실행해도 기존 순서와 멱등성이 유지됐습니다.

## 실행 이력 확인

```bash
.venv/bin/retail-runs --date 2009-12-01 --limit 3
.venv/bin/retail-runs --date 2009-12-02 --limit 3
.venv/bin/retail-runs --date 2009-12-03 --limit 3
```
