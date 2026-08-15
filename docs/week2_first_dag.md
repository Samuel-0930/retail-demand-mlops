# Week 2 첫 수동 날짜 DAG

첫 Airflow DAG인 `retail_daily_ingestion`은 사용자가 입력한 날짜 하루만 처리합니다.
아직 자동 일정은 켜지 않았기 때문에 Airflow를 시작해도 과거 날짜가 한꺼번에
실행되지 않습니다.

## DAG 구조

1. `resolve_target_date`: 입력값이 `YYYY-MM-DD` 형식의 실제 날짜인지 확인
2. `load_and_validate_daily_sales`: Week 1의 일일 pipeline을 그대로 호출해 적재 후 검증

DAG 파일에는 CSV 처리나 SQL 로직을 복사하지 않습니다. Airflow는 작업 순서와
재시도만 관리하고, 실제 데이터 처리는 이미 테스트한 Python 코드가 담당합니다.

## 환경 준비

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
source scripts/airflow_env.sh
.airflow-venv/bin/airflow db migrate
```

첫 명령은 `.env`의 PostgreSQL 설정과 프로젝트 안의 Airflow 경로를 현재 터미널에
적용합니다. 두 번째 명령은 Airflow가 실행 기록을 저장할 로컬 metadata DB를
준비합니다. 이 SQLite DB는 판매 데이터 저장소가 아니며 `.airflow/` 아래에 있어
Git에 포함되지 않습니다.

## 안전한 구조 확인

```bash
.airflow-venv/bin/airflow dags list-import-errors --output json
.airflow-venv/bin/airflow dags list --local --output plain
PYTHONPATH=src .airflow-venv/bin/python \
  -m unittest discover -s tests/airflow -v
```

첫 명령의 결과가 `[]`이면 Python import 오류가 없다는 뜻입니다. 두 번째 목록에는
`retail_daily_ingestion`이 보여야 합니다. 테스트는 자동 일정이 꺼져 있는지, 두
task가 올바른 순서인지, 잘못된 날짜를 거부하는지 확인합니다.

## 하루치 수동 실행

다음 명령은 scheduler나 웹 화면을 계속 실행하지 않고, DAG의 두 task를 현재
터미널에서 한 번 순서대로 실행합니다.

```bash
.airflow-venv/bin/airflow dags test retail_daily_ingestion \
  --conf '{"target_date":"2009-12-01"}'
```

`dags test`의 test는 가짜 데이터로 흉내만 낸다는 뜻이 아닙니다. task가 연결한 실제
Python pipeline과 PostgreSQL을 사용하므로, 실행 전 `.env`의 데이터베이스를 반드시
확인해야 합니다. 다만 scheduler와 웹 서버 없이 DAG 한 건을 로컬에서 점검한다는
점이 일반 운영 실행과 다릅니다.

## 확인된 결과

2026-08-16에 `2009-12-01`을 입력해 실행한 결과는 다음과 같습니다.

| 항목 | 결과 |
|---|---:|
| Airflow DAG 상태 | `success` |
| 입력 행 | 3,223 |
| 새로 삽입된 행 | 0 |
| 기존 행으로 건너뛴 행 | 3,223 |
| 검증된 PostgreSQL 행 | 3,223 |

이미 Week 1에서 해당 날짜가 적재돼 있었기 때문에 새 행은 추가되지 않았습니다.
3,223행을 모두 기존 데이터로 판단하고 최종 행 수도 3,223행으로 유지했으므로,
DAG가 기존 멱등 적재 규칙을 깨지 않고 호출했다는 뜻입니다.

최근 적재 이력은 다음 명령으로 다시 확인할 수 있습니다.

```bash
.venv/bin/retail-runs --date 2009-12-01 --limit 3
```
