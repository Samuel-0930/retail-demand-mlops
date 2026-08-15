# Week 2 Airflow 운영 Runbook

이 문서는 Week 1 Python pipeline을 Airflow에서 안전하게 확인하고 운영하기 위한
절차입니다. Airflow는 작업 순서와 실행 상태를 관리하며, 실제 판매 데이터는 계속
PostgreSQL의 `raw`, `ops` 스키마에 저장됩니다.

## 1. DAG 역할

| DAG | 용도 | 자동 일정 |
|---|---|---|
| `retail_daily_ingestion` | 과거 날짜 하루 수동 처리·복구 | 없음 |
| `retail_backfill_ingestion` | 최대 3일 수동 순차 처리 | 없음 |
| `retail_daily_simulation` | 현재 하루 구간을 과거 날짜로 자동 재생 | 매일 자정, 최초 pause |

수동 DAG와 자동 DAG를 구분해 사용합니다. 자동 DAG를 과거 날짜 임의 실행에
사용하지 않고, 복구는 수동 일일 DAG나 backfill DAG로 수행합니다.

## 2. 사전 조건

- Week 1 전체 pipeline과 PostgreSQL 적재 검증 완료
- `data/processed/online_retail_II.csv`와 manifest 존재
- PostgreSQL 실행 중
- 프로젝트 최상위 디렉터리에서 명령 실행
- Python 3.13 Airflow 전용 환경

## 3. 설치와 환경 설정

```bash
./scripts/setup_airflow.sh
```

`.env`에는 PostgreSQL 접속 정보와 다음 시뮬레이션 기준 날짜가 필요합니다.

```dotenv
RETAIL_SIMULATION_SCHEDULE_START_DATE=2026-08-16
RETAIL_SIMULATION_SOURCE_START_DATE=2009-12-01
RETAIL_SIMULATION_SOURCE_END_DATE=2011-12-09
```

새 터미널마다 Airflow와 `.env` 설정을 함께 불러옵니다.

```bash
source scripts/airflow_env.sh
```

소스 코드가 바뀌었다면 Airflow 전용 환경에도 프로젝트를 다시 설치합니다.

```bash
.airflow-venv/bin/python -m pip install .
```

## 4. metadata DB와 DAG 등록

```bash
.airflow-venv/bin/airflow db migrate
.airflow-venv/bin/airflow dags reserialize
.airflow-venv/bin/airflow dags list-import-errors --local --output json
.airflow-venv/bin/airflow dags list --output plain
```

정상 상태는 다음과 같습니다.

- import 오류 결과가 `[]`
- 세 DAG가 모두 목록에 존재
- `retail_daily_simulation`의 `is_paused`가 `True`

`.airflow/airflow.db`는 Airflow 실행 기록용 SQLite DB입니다. 판매 데이터를 저장하는
PostgreSQL과 역할이 다르며 Git에 포함되지 않습니다.

## 5. 테스트

핵심 pipeline 테스트는 가벼운 기본 환경에서 실행합니다.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Airflow DAG 전용 테스트는 별도 환경에서 실행합니다.

```bash
PYTHONPATH=src .airflow-venv/bin/python \
  -m unittest discover -s tests/airflow -v
```

현재 기준으로 기본 테스트는 63개 중 Airflow 전용 10개를 제외하고 통과하며,
Airflow 환경에서는 DAG 전용 테스트 10개가 모두 실행됩니다.

## 6. 하루 수동 실행

```bash
.airflow-venv/bin/airflow dags test retail_daily_ingestion \
  --conf '{"target_date":"2009-12-01"}'
```

이 명령은 실제 PostgreSQL pipeline을 실행합니다. 이미 적재된 날짜라면
`inserted=0`, `skipped=3223`이 정상적인 멱등 결과입니다.

## 7. 최대 3일 backfill

```bash
.airflow-venv/bin/airflow dags test retail_backfill_ingestion \
  --conf '{"start_date":"2009-12-01","end_date":"2009-12-03"}'
```

4일 이상은 실행 전에 거부합니다. 한 날짜가 실패하면 이후 날짜를 처리하지 않으며,
재실행 시 앞서 성공한 날짜의 중복 행은 건너뜁니다.

## 8. 자동 DAG 시작 전 점검

자동 DAG는 현재 pause 상태를 유지합니다. unpause 전 다음 항목을 모두 확인합니다.

1. `.env`의 PostgreSQL이 실습 대상 데이터베이스인지 확인
2. 시뮬레이션 기준 날짜 3개 확인
3. DAG import 오류 0건 확인
4. 자동 DAG `is_paused=True` 확인
5. `retail-runs --status failed`로 미해결 실패 확인
6. 첫 매핑이 `2026-08-16` → `2009-12-01`인지 테스트 확인

Airflow 전체 로컬 구성요소와 웹 화면을 시작하려면 별도 터미널에서 실행합니다.

```bash
source scripts/airflow_env.sh
.airflow-venv/bin/airflow standalone
```

standalone 명령이 출력한 주소와 로그인 정보를 사용합니다. 자동 실행을 실제로
허용하기로 결정한 뒤에만 다른 터미널에서 다음 명령을 실행합니다.

```bash
source scripts/airflow_env.sh
.airflow-venv/bin/airflow dags unpause retail_daily_simulation
```

이번 단계에서는 unpause하지 않습니다.

## 9. 중지와 복구

예상하지 않은 실행이나 실패가 보이면 자동 DAG를 먼저 중지합니다.

```bash
.airflow-venv/bin/airflow dags pause retail_daily_simulation
.venv/bin/retail-runs --status failed
.venv/bin/retail-runs --limit 10
```

실패 날짜 하나는 수동 일일 DAG로, 최대 3일은 backfill DAG로 복구합니다. 데이터나
테이블을 삭제하지 않고 같은 날짜를 재실행합니다. 멱등 기본키가 이미 성공한 행의
중복 저장을 막습니다.

## 10. GitHub Actions 분리

- `tests.yml`: 프로젝트 설치와 기본 단위 테스트를 빠르게 실행
- `airflow-dags.yml`: Airflow 3.3.0을 공식 constraints로 설치하고 DAG 전용 테스트와
  세 DAG import를 확인

Airflow CI는 로컬 PostgreSQL이나 실제 CSV에 접근하지 않고 DAG 구조와 날짜 계약만
검사합니다. 따라서 GitHub Actions 성공은 실제 데이터 적재 성공을 의미하지 않으며,
PostgreSQL 검증은 로컬 Runbook 절차로 별도 확인합니다.

## 11. 알려진 경고

`Could not import graphviz` 경고는 DAG 그림 파일을 렌더링할 수 없다는 뜻입니다.
현재 task 실행, 날짜 매핑, PostgreSQL 적재에는 필요하지 않으므로 graphviz를 추가로
설치하지 않습니다.

## 12. Week 2 완료 범위

- 수동 일일 DAG 실행·재실행 검증
- 최대 3일 순차 backfill 검증
- 일일 data interval과 과거 판매 날짜 매핑
- pause 상태 자동 DAG 등록
- 기본 CI와 Airflow DAG CI 분리
- 운영·중지·복구 절차 문서화

자동 DAG의 실제 unpause와 상시 scheduler 운영은 데이터베이스와 실행 시점을 사람이
최종 확인한 뒤 수행하는 운영 작업으로 남깁니다.
