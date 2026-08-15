# Retail Demand MLOps

[![Unit tests](https://github.com/Samuel-0930/retail-demand-mlops/actions/workflows/tests.yml/badge.svg)](https://github.com/Samuel-0930/retail-demand-mlops/actions/workflows/tests.yml)

리테일 수요 데이터를 안정적으로 수집·검증·적재하는 과정을 보여주기 위한
Data Engineering 중심 포트폴리오 프로젝트입니다.

## Current Scope

Week 1 데이터 적재 기반은 완료됐고, Week 2 Airflow orchestration을 시작했습니다.

```text
UCI Online Retail II XLSX
  → read-only schema profiling
  → canonical CSV normalization
  → daily batch simulator
  → PostgreSQL COPY ingestion
```

Airflow는 수동 날짜 한 건을 처리하는 첫 DAG와 PostgreSQL 연동 실행까지
확인했습니다. dbt, MLflow, LightGBM, FastAPI는 아직 포함하지 않습니다.

## Implemented

- 공식 UCI 원본의 멱등 다운로드와 SHA-256 무결성 검증
- XLSX 읽기 전용 스트리밍 프로파일링
- 두 시트의 22,523개 중복 구간을 제외한 표준 CSV 변환
- 익명 주문과 취소·반품·가격 품질 플래그 보존
- 날짜별 CSV 배치 시뮬레이터
- 환경변수 기반 PostgreSQL 설정 계약
- 재적재 중복을 방지하는 `raw.retail_sales` DDL
- 임시 테이블과 `ON CONFLICT`를 사용하는 멱등 PostgreSQL COPY loader
- 성공·실패·처리 행 수를 기록하는 `ops.ingestion_runs` 실행 이력
- 하루치 적재 후 결과를 확인하는 일일 pipeline
- 시작일과 종료일을 포함해 날짜순으로 처리하는 backfill pipeline
- 최근 적재 성공·실패와 처리 행 수를 보여주는 읽기 전용 운영 조회
- push와 pull request마다 단위 테스트를 실행하는 GitHub Actions CI
- 공식 constraints를 사용하는 Airflow 3.3.0 전용 환경 설치 스크립트
- 날짜 검증 뒤 기존 일일 pipeline을 호출하는 수동 실행 Airflow DAG
- Airflow DAG의 `2009-12-01` 적재·검증 성공 확인
- 같은 Airflow DAG 연속 실행의 PostgreSQL 멱등성 확인
- 최대 3일을 날짜순으로 처리하는 수동 Airflow backfill DAG

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
cp .env.example .env
```

`.env`를 자신의 PostgreSQL 접속 정보로 수정한 뒤 새 터미널마다 설정을
불러옵니다.

```bash
set -a
source .env
set +a
```

소스 코드를 변경한 뒤 CLI로 확인할 때는 설치 명령을 다시 실행합니다.

처음부터 순서대로 실행하거나 문제를 해결할 때는
[Week 1 운영 Runbook](docs/week1_runbook.md)을 확인합니다.

## Commands

```bash
# 공식 원본 다운로드
.venv/bin/retail-download

# 읽기 전용 스키마 프로파일 생성
.venv/bin/retail-profile

# 표준 CSV 생성
.venv/bin/retail-transform

# 기존 PostgreSQL 데이터베이스에 raw·ops 스키마 적용
.venv/bin/retail-db-setup

# 환경변수에 지정한 PostgreSQL로 CSV 적재
.venv/bin/retail-load

# 지정 날짜의 배치만 PostgreSQL로 적재
.venv/bin/retail-load --date 2009-12-01

# manifest와 PostgreSQL 전체 적재 결과 비교
.venv/bin/retail-validate

# simulator 기대값과 PostgreSQL 하루치 배치 비교
.venv/bin/retail-validate --date 2009-12-01

# 하루치 적재와 검증을 순서대로 실행
.venv/bin/retail-daily --date 2009-12-01

# 지정한 날짜 범위의 일일 pipeline을 순서대로 실행
.venv/bin/retail-backfill --start-date 2009-12-01 --end-date 2009-12-03

# PostgreSQL의 최근 적재 실행 10개를 읽기 전용으로 조회
.venv/bin/retail-runs --limit 10

# 실패한 실행 또는 특정 날짜의 실행만 조회
.venv/bin/retail-runs --status failed
.venv/bin/retail-runs --date 2009-12-01

# 전체 테스트
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

원본 XLSX와 생성된 CSV는 용량과 재배포 문제를 피하기 위해 Git에서 제외합니다.

## Design Decisions

- [날짜별 검증에 기존 날짜 인덱스를 유지한 근거](docs/decisions/001_keep_sale_date_index.md)
- [Airflow를 별도 런타임으로 분리한 근거](docs/decisions/002_airflow_runtime_boundary.md)
- [Airflow backfill을 최대 3일 순차 실행으로 시작하는 근거](docs/decisions/003_sequential_airflow_backfill.md)
- [Airflow 일일 schedule을 과거 판매 날짜에 매핑하는 근거](docs/decisions/004_daily_simulation_schedule.md)

## Roadmap

- Week 1: Python ingestion, PostgreSQL, 검증, 운영 이력 — 완료
- Week 2: Airflow 수동 날짜 DAG부터 schedule까지 — 진행 중
- 이후: dbt 데이터 모델링 → MLflow·LightGBM → FastAPI

[Week 2 세부 계획](docs/week2_plan.md)

[Airflow 전용 환경 설치 방법](docs/week2_airflow_setup.md)

[첫 수동 날짜 DAG 구조와 확인 방법](docs/week2_first_dag.md)

[최대 3일 Airflow backfill DAG 실행 방법](docs/week2_backfill_dag.md)

## Dataset

[UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii)를
사용합니다. 데이터셋은 CC BY 4.0 라이선스로 제공됩니다.
