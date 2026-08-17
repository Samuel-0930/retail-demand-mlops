#!/usr/bin/env bash

# 이 파일은 현재 셸의 환경변수를 바꿔야 하므로 실행하지 않고 source해야 한다.
is_sourced=false
if [[ -n "${ZSH_EVAL_CONTEXT:-}" ]]; then
    [[ "${ZSH_EVAL_CONTEXT}" == *:file ]] && is_sourced=true
elif [[ -n "${BASH_VERSION:-}" ]]; then
    [[ "${BASH_SOURCE[0]}" != "$0" ]] && is_sourced=true
fi

if [[ "${is_sourced}" != true ]]; then
    echo "source scripts/dbt_env.sh 형태로 실행하세요." >&2
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
if [[ ! -x "${PROJECT_ROOT}/.dbt-venv/bin/dbt" ]]; then
    echo ".dbt-venv가 없습니다. 먼저 ./scripts/setup_dbt.sh를 실행하세요." >&2
    return 1
fi

export DBT_PROFILES_DIR="${PROJECT_ROOT}/.dbt"

# .env의 DB 설정을 dbt 프로세스에도 전달하되 기존 allexport 상태는 보존한다.
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

echo "DBT_PROFILES_DIR=${DBT_PROFILES_DIR}"
