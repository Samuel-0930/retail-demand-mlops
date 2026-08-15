# Airflow 소규모 backfill 실행 단위 결정

## 배경

Week 1의 `run_backfill_pipeline()`은 시작일과 종료일을 받아 하루씩 날짜순으로
`run_daily_pipeline()`을 호출합니다. 각 날짜는 별도 PostgreSQL 트랜잭션과
`ops.ingestion_runs` 이력을 만들며, 한 날짜가 실패하면 이후 날짜를 처리하지
않습니다.

Airflow에서는 이 기존 함수를 한 task가 호출하는 방식과 날짜마다 동적 task를
만드는 방식을 선택할 수 있습니다.

## 비교한 방식

### 하나의 순차 backfill task

- 기존에 테스트한 날짜순 실행과 실패 시 중단 계약을 그대로 사용합니다.
- 현재 표준 CSV는 날짜별 파일이 아니므로 동시에 여러 날짜를 실행해도 각 task가
  전체 CSV를 다시 읽어야 합니다.
- Airflow 화면에는 backfill 전체가 하나의 실행 단위로 보이지만, 날짜별 처리 결과는
  기존 `ops.ingestion_runs`에서 확인할 수 있습니다.

### 날짜별 동적 task mapping

- Airflow 화면에서 날짜별 성공과 실패를 각각 확인하고 특정 날짜만 재시도하기
  쉽습니다.
- 실행 시 생성된 날짜 목록을 `expand()`로 여러 task instance로 만들 수 있습니다.
- 현재 구조에서는 task 실행 순서가 핵심 계약인데, 동적 mapping은 독립 task를
  만드는 기능이라 기존의 “실패 뒤 날짜는 실행하지 않음”을 그대로 보장하기
  어렵습니다.
- 병렬 실행하면 하나의 큰 CSV를 여러 번 동시에 읽고 로컬 PostgreSQL에도 여러
  적재가 동시에 접근합니다.

## 결정

첫 Airflow backfill은 **하나의 task가 기존 `run_backfill_pipeline()`을 호출해
날짜순으로 처리**합니다.

안전 범위는 다음과 같이 제한합니다.

- `start_date`와 `end_date`를 수동으로 입력
- 시작일과 종료일을 모두 포함
- 한 번에 최대 3일
- `schedule=None`, `catchup=False`
- 동시에 하나의 DAG run만 허용
- 첫 검증 범위는 `2009-12-01`부터 `2009-12-03`

최대 3일 제한은 실수로 전체 과거 기간을 실행하는 것을 막는 운영 안전장치입니다.
중간 날짜에서 실패해 DAG 전체를 다시 실행하더라도 앞서 성공한 날짜는 기존 멱등
적재가 중복을 건너뜁니다.

## 감수하는 제한

- Airflow 화면에서는 날짜별 task 상태가 아니라 backfill 전체 task 상태가 보입니다.
- 특정 날짜만 다시 처리하려면 범위를 그 날짜 하루로 입력해야 합니다.
- 재실행 시 앞서 성공한 날짜도 다시 읽지만 PostgreSQL에는 중복 저장하지 않습니다.

## 재검토 조건

다음 중 하나가 충족되면 날짜별 동적 task mapping으로 전환할지 다시 검토합니다.

- 표준 데이터가 날짜별 파일이나 object storage partition으로 분리될 때
- 날짜별 Airflow 재시도와 UI 가시성이 운영상 반드시 필요할 때
- 여러 worker와 PostgreSQL의 동시 적재 부하를 측정할 환경이 준비될 때
- 3일보다 큰 범위를 자주 backfill해야 할 때

## 공식 참고 자료

- [Airflow Dynamic Task Mapping](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html)
- [Airflow Task 개념](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html)
