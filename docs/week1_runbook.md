# Week 1 운영 Runbook

이 문서는 새 컴퓨터나 새 터미널에서 Week 1 pipeline을 같은 순서로 다시 실행하기
위한 안내서입니다. Airflow 없이 사람이 명령을 실행하는 현재 범위만 다룹니다.

## 1. 전체 흐름

```text
UCI XLSX 다운로드
  → 원본 프로파일링
  → 표준 CSV와 manifest 생성
  → PostgreSQL 테이블 준비
  → 전체 또는 날짜별 적재
  → 적재 결과 검증
  → 실행 이력 확인
```

`manifest`는 CSV의 행 수, 컬럼, 체크섬을 기록한 확인서입니다. loader는 이
확인서와 실제 CSV가 다르면 PostgreSQL 적재를 시작하지 않습니다.

## 2. 사전 준비

- Python 3.11 이상
- 실행 중인 PostgreSQL
- 미리 생성한 PostgreSQL 데이터베이스와 접속 가능한 사용자
- 원본 다운로드를 위한 인터넷 연결

`retail-db-setup`은 기존 데이터베이스 안에 `raw`, `ops` 스키마와 테이블을
만듭니다. PostgreSQL 서버, 데이터베이스, 사용자를 새로 만들지는 않습니다.

## 3. 프로젝트 설치

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

소스 코드를 변경했다면 CLI가 변경 내용을 사용하도록 마지막 설치 명령을 다시
실행합니다.

## 4. PostgreSQL 환경 설정

예제 파일을 복사한 뒤 자신의 PostgreSQL 접속 정보로 수정합니다.

```bash
cp .env.example .env
```

```dotenv
RETAIL_DB_HOST=localhost
RETAIL_DB_PORT=5432
RETAIL_DB_NAME=retail_demand
RETAIL_DB_USER=retail_app
RETAIL_DB_PASSWORD=change-me
```

`.env`는 Git에 저장되지 않습니다. 실제 비밀번호를 `.env.example`이나 README에
작성하지 않습니다.

새 터미널을 열 때마다 다음 명령으로 설정을 현재 터미널에 전달합니다.

```bash
set -a
source .env
set +a
```

`.env` 파일은 자동으로 읽히지 않습니다. 설정을 불러오지 않으면
`RETAIL_DB_NAME이 필요합니다`와 같은 오류가 발생합니다.

## 5. 최초 전체 실행

### 5.1 원본 다운로드

```bash
.venv/bin/retail-download
```

검증된 원본이 이미 있으면 다시 다운로드하지 않고 체크섬만 확인합니다.

### 5.2 원본 프로파일링

```bash
.venv/bin/retail-profile
```

XLSX를 변경하지 않고 컬럼, 행 수, 결측치와 데이터 품질을 JSON으로 기록합니다.

### 5.3 표준 CSV 생성

```bash
.venv/bin/retail-transform
```

두 시트의 겹치는 구간을 제거하고 표준 CSV와 manifest를 만듭니다. 현재 데이터의
기대 행 수는 `1,044,848`입니다. 출력 체크섬이 이미 manifest와 일치하면 파일을
다시 만들지 않습니다.

### 5.4 PostgreSQL 구조 적용

```bash
.venv/bin/retail-db-setup
```

번호가 붙은 SQL을 순서대로 적용합니다. `IF NOT EXISTS`를 사용하므로 같은 구조에
다시 실행해도 기존 테이블을 삭제하지 않습니다.

### 5.5 전체 CSV 적재

```bash
.venv/bin/retail-load
```

첫 실행에서는 신규 행이 PostgreSQL에 들어갑니다. 같은 파일을 다시 실행하면
복합 기본키가 중복을 막으므로 `inserted=0`, `skipped=1044848`이 정상입니다.

### 5.6 전체 적재 검증

```bash
.venv/bin/retail-validate
```

manifest의 행 수·행 번호 범위와 PostgreSQL 결과를 비교합니다. 이 명령은
PostgreSQL 데이터를 수정하지 않습니다.

### 5.7 실행 이력 확인

```bash
.venv/bin/retail-runs --limit 10
```

`inserted`는 새로 저장한 행, `skipped`는 이미 존재해 건너뛴 행, `SECONDS`는
실행에 걸린 시간입니다. `batch_date`가 `-`이면 전체 CSV 적재입니다.

## 6. 날짜별 운영

하루치 데이터를 적재한 뒤 즉시 같은 날짜를 검증합니다.

```bash
.venv/bin/retail-daily --date 2009-12-01
```

여러 날짜를 시작일부터 종료일까지 하루씩 처리합니다.

```bash
.venv/bin/retail-backfill \
  --start-date 2009-12-01 \
  --end-date 2009-12-03
```

backfill 중 한 날짜가 실패하면 이후 날짜는 실행하지 않습니다. 앞에서 성공한
날짜는 이미 commit되며, 명령을 다시 실행해도 중복 행은 건너뜁니다.

특정 날짜나 실패한 실행만 확인할 수 있습니다.

```bash
.venv/bin/retail-runs --date 2009-12-01
.venv/bin/retail-runs --status failed
```

## 7. DBeaver 확인 SQL

판매 데이터의 처음 10행을 확인합니다.

```sql
SELECT *
FROM raw.retail_sales
ORDER BY source_file_sha256, source_row_number
LIMIT 10;
```

최근 적재 이력을 확인합니다.

```sql
SELECT *
FROM ops.ingestion_runs
ORDER BY run_id DESC
LIMIT 10;
```

## 8. 자동 테스트

로컬 전체 단위 테스트를 실행합니다. 테스트는 실제 PostgreSQL 데이터를 수정하지
않습니다.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

GitHub에서는 `main` push와 pull request마다 같은 테스트를 자동 실행합니다.

## 9. 문제 해결

### `RETAIL_DB_NAME이 필요합니다`

현재 터미널에 `.env`가 전달되지 않은 상태입니다.

```bash
set -a; source .env; set +a
```

### PostgreSQL 연결 거부

PostgreSQL이 실행 중인지 확인하고 `.env`의 host, port, database, user가 DBeaver
연결 정보와 같은지 비교합니다.

### CSV 체크섬과 manifest 불일치

CSV가 manifest 생성 이후 변경됐다는 의미입니다. 원본 XLSX 체크섬을 먼저
확인한 뒤 `retail-transform`을 다시 실행합니다. CSV나 manifest를 손으로
수정하지 않습니다.

### CLI 명령이 없거나 변경한 코드가 반영되지 않음

프로젝트를 다시 설치합니다.

```bash
.venv/bin/python -m pip install --force-reinstall --no-deps .
```

## 10. 안전 원칙

- 정상 재실행에는 테이블 삭제나 `TRUNCATE`가 필요하지 않습니다.
- 전체를 처음부터 실습하려면 운영 중인 테이블을 지우기보다 새 데이터베이스를
  만들어 실행하는 편이 안전합니다.
- 원본 XLSX, 생성 CSV, `.env`는 Git에 올리지 않습니다.
- 적재 후에는 반드시 `retail-validate` 또는 `retail-daily`의 검증을 확인합니다.

