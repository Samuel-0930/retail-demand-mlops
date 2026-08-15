# Week 2 Airflow 설치

Airflow는 핵심 pipeline의 `.venv`와 분리된 `.airflow-venv`에 설치합니다.

## 설치

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
./scripts/setup_airflow.sh
```

스크립트는 다음 작업만 수행합니다.

1. Python 3.13인지 확인
2. `.airflow-venv`가 없으면 생성
3. Airflow 3.3.0을 공식 Python 3.13 constraints로 설치
4. 같은 환경에 현재 프로젝트 패키지 설치
5. `airflow version` 출력

같은 버전이 이미 설치돼 있으면 `pip`가 만족된 패키지를 재사용하므로 다시 실행할
수 있습니다.

## 수동 확인

```bash
.airflow-venv/bin/airflow version
.airflow-venv/bin/python -c \
  "from retail_demand_mlops.ingestion.daily_pipeline import run_daily_pipeline; print('project import: OK')"
```

Airflow runtime 파일은 프로젝트 내부 `.airflow`에 두며 Git에는 저장하지
않습니다. 환경 설정과 첫 DAG 확인 방법은
[첫 수동 날짜 DAG](week2_first_dag.md)를 참고합니다.

## 문제 해결

### Python 버전 오류

기본 `python3`가 3.13이 아니면 설치된 Python 3.13 경로를 지정합니다.

```bash
PYTHON_BIN=/path/to/python3.13 ./scripts/setup_airflow.sh
```

### 기존 `.airflow-venv`의 Python 버전 불일치

가상환경은 생성할 때 사용한 Python 버전을 유지합니다. 다른 Python으로 덮어쓰지
말고 `.airflow-venv`를 새로 만드는 것이 안전합니다.
