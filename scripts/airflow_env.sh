#!/usr/bin/env bash

# 이 파일은 현재 셸의 환경변수를 바꿔야 하므로 실행하지 않고 source해야 한다.
is_sourced=false
if [[ -n "${ZSH_EVAL_CONTEXT:-}" ]]; then
    [[ "${ZSH_EVAL_CONTEXT}" == *:file ]] && is_sourced=true
elif [[ -n "${BASH_VERSION:-}" ]]; then
    [[ "${BASH_SOURCE[0]}" != "$0" ]] && is_sourced=true
fi

if [[ "${is_sourced}" != true ]]; then
    echo "source scripts/airflow_env.sh 형태로 실행하세요." >&2
    exit 1
fi

PROJECT_ROOT="$(pwd)"
if [[ ! -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    echo "프로젝트 최상위 디렉터리에서 source하세요." >&2
    return 1
fi
if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    echo ".env 파일이 없습니다. .env.example을 복사해 먼저 설정하세요." >&2
    return 1
fi

export AIRFLOW_HOME="${PROJECT_ROOT}/.airflow"
export AIRFLOW__CORE__DAGS_FOLDER="${PROJECT_ROOT}/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES="False"

# .env의 DB 설정을 자식 Airflow 프로세스에도 전달하되 기존 allexport 상태는 보존한다.
restore_allexport="false"
if [[ "${-}" != *a* ]]; then
    set -a
    restore_allexport="true"
fi
source "${PROJECT_ROOT}/.env"
if [[ "${restore_allexport}" == "true" ]]; then
    set +a
fi
unset restore_allexport
unset is_sourced

echo "AIRFLOW_HOME=${AIRFLOW_HOME}"
echo "AIRFLOW__CORE__DAGS_FOLDER=${AIRFLOW__CORE__DAGS_FOLDER}"
