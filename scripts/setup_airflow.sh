#!/usr/bin/env bash

set -euo pipefail

# Airflow와 공식 constraints 버전을 함께 고정해 설치 결과가 달라지는 범위를 줄인다.
AIRFLOW_VERSION="3.3.0"
PYTHON_VERSION="3.13"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIRFLOW_VENV="${PROJECT_ROOT}/.airflow-venv"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

detected_python_version="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${detected_python_version}" != "${PYTHON_VERSION}" ]]; then
    echo "Python ${PYTHON_VERSION}이 필요하지만 ${detected_python_version}이 감지됐습니다." >&2
    echo "필요하면 PYTHON_BIN 환경변수로 Python 실행 파일을 지정하세요." >&2
    exit 1
fi

if [[ ! -x "${AIRFLOW_VENV}/bin/python" ]]; then
    "${PYTHON_BIN}" -m venv "${AIRFLOW_VENV}"
fi

venv_python_version="$(${AIRFLOW_VENV}/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${venv_python_version}" != "${PYTHON_VERSION}" ]]; then
    echo "기존 .airflow-venv의 Python 버전이 ${venv_python_version}입니다." >&2
    echo "별도 환경을 제거한 뒤 Python ${PYTHON_VERSION}으로 다시 실행하세요." >&2
    exit 1
fi

# 핵심 프로젝트 환경과 분리된 venv에만 Airflow와 프로젝트 패키지를 설치한다.
"${AIRFLOW_VENV}/bin/python" -m pip install \
    "apache-airflow==${AIRFLOW_VERSION}" \
    --constraint "${CONSTRAINT_URL}"
"${AIRFLOW_VENV}/bin/python" -m pip install \
    "${PROJECT_ROOT}" \
    --constraint "${CONSTRAINT_URL}"

echo "Airflow 전용 환경 설치 완료"
"${AIRFLOW_VENV}/bin/airflow" version
