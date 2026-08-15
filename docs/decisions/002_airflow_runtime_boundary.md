# Airflow 런타임 분리 결정

## 배경

Week 1에서는 사람이 CLI를 실행해 날짜별 적재와 검증을 수행했습니다. Week 2의
목표는 이미 검증된 Python pipeline을 Airflow가 실행하도록 연결하는 것입니다.
Airflow 안에서 loader나 validator를 다시 구현하지 않습니다.

## 확인한 공식 계약

- Apache Airflow 3.3.0은 Python 3.10~3.14를 지원합니다.
- 재현 가능한 `pip` 설치에는 Airflow 버전과 Python 버전에 맞는 constraints 파일을
  사용하는 방식이 권장됩니다.
- Airflow 3 DAG 작성은 안정적인 공개 인터페이스인 `airflow.sdk`를 사용합니다.
- 일일 schedule은 해당 날짜 구간이 끝난 뒤 실행되므로 데이터 날짜는 단순한 실제
  실행 시각이 아니라 Airflow의 data interval을 기준으로 판단해야 합니다.

## 결정

### 1. Airflow는 별도 가상환경에 설치

기존 `.venv`는 다운로드, 변환, 적재와 단위 테스트를 위한 가벼운 환경으로
유지합니다. Airflow는 `.airflow-venv`에 고정 버전과 공식 constraints로 설치합니다.

이렇게 하면 Airflow의 많은 의존성이 핵심 pipeline의 설치와 CI 속도에 영향을
주지 않습니다. `.airflow-venv`는 생성 가능한 로컬 파일이므로 Git에 저장하지
않습니다.

### 2. 첫 단계에서는 Docker를 사용하지 않음

현재 판매 데이터와 PostgreSQL이 로컬 컴퓨터에 있고 Unix socket도 사용합니다.
Docker를 바로 추가하면 파일 mount와 네트워크 연결이라는 별도 문제까지 동시에
생깁니다. 먼저 Airflow standalone으로 DAG 계약을 검증하고, 배포 환경이 필요할 때
Docker를 별도 단계로 검토합니다.

### 3. DAG는 기존 Python 함수를 호출

DAG task는 `run_daily_pipeline()`을 호출하는 얇은 orchestration 계층으로 만듭니다.
적재, 멱등성, 감사 이력, 검증 로직은 기존 모듈이 계속 책임집니다.

```text
Airflow DAG
  → 대상 날짜 결정
  → DatabaseSettings 생성
  → run_daily_pipeline(...)
  → 기존 ops.ingestion_runs에서 결과 확인
```

### 4. 첫 DAG는 수동 날짜 1개만 처리

현재 데이터는 2009~2011년의 과거 데이터입니다. 처음부터 `@daily`와 catchup을
활성화하면 수백 개 날짜가 한꺼번에 실행될 수 있습니다. 첫 DAG는 schedule 없이
수동으로 `target_date`를 받아 `2009-12-01` 하루만 검증합니다.

Airflow 연결이 확인된 뒤 별도 단계에서 작은 날짜 범위 backfill과 실제 schedule을
설계합니다.

### 5. Airflow metadata와 판매 DB를 분리

Airflow standalone의 metadata DB는 Airflow 자체 실행 상태만 관리합니다. 판매
데이터는 기존 `retail_demand` PostgreSQL의 `raw`, `ops` 스키마에 계속 저장합니다.
두 데이터베이스의 역할을 섞지 않습니다.

## 첫 DAG 완료 조건

- Airflow가 DAG를 import 오류 없이 발견한다.
- 수동 입력 `target_date=2009-12-01`로 DAG 실행이 성공한다.
- PostgreSQL의 해당 날짜 3,223행 검증이 통과한다.
- 재실행 시 `inserted=0`, `skipped=3223`으로 멱등성이 유지된다.
- Airflow가 없는 기본 `.venv`에서도 기존 단위 테스트가 계속 통과한다.

## 이번 결정에서 하지 않는 것

- Docker Compose 기반 Airflow 배포
- CeleryExecutor, KubernetesExecutor와 분산 worker
- 과거 전체 기간 자동 catchup
- dbt, MLflow, LightGBM, FastAPI 연결

## 공식 참고 자료

- [Airflow 3.3.0 Quick Start](https://airflow.apache.org/docs/apache-airflow/stable/start.html)
- [Airflow PyPI constraints 설치](https://airflow.apache.org/docs/apache-airflow/stable/installation/installing-from-pypi.html)
- [Airflow 3 공개 인터페이스](https://airflow.apache.org/docs/apache-airflow/stable/public-airflow-interface.html)
- [DAG와 data interval](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html)
