# Retail Demand MLOps

리테일 수요 데이터를 안정적으로 수집·검증·적재하는 과정을 보여주기 위한
Data Engineering 중심 포트폴리오 프로젝트입니다.

## Current Scope

현재 Week 1 범위만 구현되어 있습니다.

```text
UCI Online Retail II XLSX
  → read-only schema profiling
  → canonical CSV normalization
  → daily batch simulator
  → PostgreSQL COPY ingestion
```

Airflow, dbt, MLflow, LightGBM, FastAPI는 아직 포함하지 않습니다.

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

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Commands

```bash
# 공식 원본 다운로드
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.download

# 읽기 전용 스키마 프로파일 생성
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.profile

# 표준 CSV 생성
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.transform

# 환경변수에 지정한 PostgreSQL로 CSV 적재
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.loader

# 지정 날짜의 배치만 PostgreSQL로 적재
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.loader --date 2009-12-01

# manifest와 PostgreSQL 전체 적재 결과 비교
PYTHONPATH=src .venv/bin/python -m retail_demand_mlops.ingestion.validate

# 전체 테스트
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

원본 XLSX와 생성된 CSV는 용량과 재배포 문제를 피하기 위해 Git에서 제외합니다.

## Dataset

[UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii)를
사용합니다. 데이터셋은 CC BY 4.0 라이선스로 제공됩니다.
