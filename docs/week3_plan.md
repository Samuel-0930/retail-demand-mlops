# Week 3 dbt 데이터 모델링 계획

Week 3의 목표는 PostgreSQL의 원본 판매 기록을 삭제하거나 덮어쓰지 않고, 향후 수요
예측에 사용할 일별 상품 단위 데이터셋을 반복 가능하게 만드는 것입니다.

## 작업 순서

1. [완료] source·staging·mart의 역할과 한 행의 의미 결정
2. [완료] dbt-postgres 전용 가상환경과 고정 설치 절차 추가
3. [다음] 최소 dbt 프로젝트와 환경변수 기반 profile 연결
4. [예정] `raw.retail_sales` source 선언과 source 테스트
5. [예정] `stg_retail_sales` 모델과 행 보존 테스트
6. [예정] 판매·반품·취소 수량 계산 규칙 테스트
7. [예정] `mart_daily_product_demand` 모델 작성
8. [예정] mart 유일키·null·집계 일치 테스트
9. [예정] Airflow와 dbt 연결 범위 결정
10. [예정] Week 3 Runbook과 dbt CI 작성

## 첫 모델 범위

```text
raw.retail_sales
  → stg_retail_sales
  → mart_daily_product_demand
```

- `raw.retail_sales`: Python ingestion이 저장한 원본에 가까운 데이터
- `stg_retail_sales`: 원본 행을 잃지 않고 이름·타입·품질 의미를 정리한 데이터
- `mart_daily_product_demand`: 날짜와 상품 코드별 판매·반품·순수량을 집계한 데이터

상세한 행 단위와 품질 처리 원칙은
[ADR 005](decisions/005_dbt_modeling_boundary.md)에 기록합니다.

## 이번 단계에서 하지 않는 것

- dbt 또는 추가 라이브러리 설치
- PostgreSQL 테이블·스키마 생성 또는 변경
- 기존 Airflow DAG 수정
- MLflow, LightGBM, FastAPI 구현
- 고객 ID가 없는 행이나 취소·반품 행 삭제

## 단계별 원칙

- dbt는 `raw`, `ops` 스키마를 읽기만 하고 결과는 `analytics` 스키마에 만듭니다.
- 모델 하나를 작성할 때 해당 데이터 계약 테스트도 함께 추가합니다.
- 원본 행을 제외하는 규칙은 staging이 아니라 목적이 명확한 mart에 둡니다.
- 비밀번호와 로컬 dbt profile은 Git에 저장하지 않습니다.
- Airflow 연결은 dbt 모델이 로컬에서 독립적으로 검증된 뒤 진행합니다.

## 현재 위치

실제 PostgreSQL DDL과 프로파일 결과를 기준으로 첫 모델의 계층, 행 단위, 취소·반품·
익명 주문 처리 원칙을 정했고, dbt를 기존 애플리케이션 환경과 분리해 설치하는
절차까지 완료했습니다. 다음 작업은 비밀번호를 저장하지 않는 dbt profile 연결입니다.
