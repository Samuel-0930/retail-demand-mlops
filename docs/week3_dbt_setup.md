# Week 3 dbt 전용 환경 설치

dbt는 기존 `.venv`나 `.airflow-venv`에 설치하지 않습니다. 각 환경이 필요로 하는
패키지 버전이 달라질 수 있으므로, dbt 전용 `.dbt-venv`를 사용합니다.

## 설치

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
./scripts/setup_dbt.sh
```

이 스크립트는 Python 3.13 전용 가상환경을 만들고 `dbt-postgres==1.11.0`,
`dbt-core==1.12.2`를 설치한 뒤 설치된 dbt 버전을 출력합니다. 설치 버전은
[dbt-postgres PyPI 배포 정보](https://pypi.org/project/dbt-postgres/)를 기준으로
고정했습니다. 어댑터와 core를 함께 고정해 재설치 시 핵심 실행 버전이 달라지지
않도록 합니다.

## 환경 불러오기

dbt가 PostgreSQL 접속 정보를 읽을 수 있도록 새 터미널마다 실행합니다.

```bash
source scripts/dbt_env.sh
```

이 명령은 `.env`를 읽고 dbt profile을 찾을 위치로 프로젝트의 `.dbt` 디렉터리를
지정합니다. 아직 profile 파일은 만들지 않았으므로, 이번 단계에서는 dbt 실행 대신
설치 버전 확인까지만 수행합니다.

```bash
.dbt-venv/bin/dbt --version
```

## 재설치와 Python 버전 변경

소스 코드 변경은 dbt 패키지 재설치가 필요하지 않습니다. dbt 어댑터 버전을 바꿀
때만 `scripts/setup_dbt.sh`의 `DBT_POSTGRES_VERSION`을 먼저 수정합니다.

Python 3.13이 아닌 실행 파일을 사용해야 한다면 다음처럼 지정합니다.

```bash
PYTHON_BIN=/path/to/python3.13 ./scripts/setup_dbt.sh
```

## 이번 단계의 범위

- dbt 전용 가상환경 생성
- PostgreSQL 어댑터 버전 고정
- `.env`와 dbt profile 경로 연결 준비

이번 단계에서는 PostgreSQL에 연결하지 않고, profile·source·model도 만들지 않습니다.
다음 단계에서 비밀번호를 Git에 저장하지 않는 dbt `profiles.yml` 연결을 추가합니다.
