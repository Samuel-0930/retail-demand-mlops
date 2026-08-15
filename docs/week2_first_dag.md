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

이 단계에서는 DAG가 읽히는 것까지만 검증했습니다. 실제 PostgreSQL 적재를 포함한
수동 실행은 다음 단계에서 `2009-12-01` 하루로 제한해 확인합니다.
