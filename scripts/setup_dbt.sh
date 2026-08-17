#!/usr/bin/env bash

set -euo pipefail

# dbt를 애플리케이션·Airflow 환경과 분리해 설치해 의존성 충돌을 방지한다.
DBT_POSTGRES_VERSION="1.11.0"
DBT_CORE_VERSION="1.12.2"
PYTHON_VERSION="3.13"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBT_VENV="${PROJECT_ROOT}/.dbt-venv"

detected_python_version="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${detected_python_version}" != "${PYTHON_VERSION}" ]]; then
    echo "Python ${PYTHON_VERSION}이 필요하지만 ${detected_python_version}이 감지됐습니다." >&2
    echo "필요하면 PYTHON_BIN 환경변수로 Python 실행 파일을 지정하세요." >&2
    exit 1
fi

if [[ ! -x "${DBT_VENV}/bin/python" ]]; then
    "${PYTHON_BIN}" -m venv "${DBT_VENV}"
fi

venv_python_version="$(${DBT_VENV}/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${venv_python_version}" != "${PYTHON_VERSION}" ]]; then
    echo "기존 .dbt-venv의 Python 버전이 ${venv_python_version}입니다." >&2
    echo "별도 환경을 제거한 뒤 Python ${PYTHON_VERSION}으로 다시 실행하세요." >&2
    exit 1
fi

# 버전을 정확히 고정해 다른 시점에도 같은 dbt 어댑터를 설치한다.
"${DBT_VENV}/bin/python" -m pip install \
    "dbt-postgres==${DBT_POSTGRES_VERSION}" \
    "dbt-core==${DBT_CORE_VERSION}"

echo "dbt 전용 환경 설치 완료"
"${DBT_VENV}/bin/dbt" --version
