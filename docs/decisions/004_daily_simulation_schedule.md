# 일일 시뮬레이션 schedule과 판매 날짜 매핑 결정

## 배경

현재 표준 CSV의 판매 날짜는 `2009-12-01`부터 `2011-12-09`까지입니다. Airflow가
실행되는 현재 날짜를 그대로 loader에 전달하면 원본에 없는 2026년 날짜를 찾게
됩니다.

현재 날짜별 검증은 원본과 PostgreSQL이 모두 0행이면 성공합니다. 따라서 현재
날짜를 잘못 전달해도 “처리할 데이터가 없었다”는 정상 빈 배치처럼 보일 수 있어,
자동 schedule을 켜기 전에 현재 날짜와 과거 원본 날짜의 관계를 명시해야 합니다.

## Airflow 날짜 의미

일일 data interval은 하루의 시작과 끝을 나타냅니다. 예를 들어 `2026-08-16`
구간은 다음 날인 `2026-08-17` 00:00 이후 실행되며, 이때 처리 대상은 실행을 시작한
날짜가 아니라 `data_interval_start`가 나타내는 `2026-08-16`입니다.

Airflow 3은 단순 cron 문자열에 기본적으로 시점 기반 timetable을 사용할 수
있습니다. 이 프로젝트는 하루 구간 자체가 필요하므로 전역 Airflow 설정에 의존하지
않고 `CronDataIntervalTimetable`을 DAG에 명시합니다.

## 결정

### 수동 DAG와 자동 DAG 분리

- `retail_daily_ingestion`은 과거 날짜를 직접 입력하는 수동 복구·검증 DAG로 유지
- 별도 `retail_daily_simulation` DAG만 자동 일일 schedule 사용
- 자동 DAG를 수동 복구 용도로 사용하지 않음

Airflow 3에서는 수동 실행의 data interval이 입력 logical date와 같다고 가정할 수
없습니다. 두 목적을 분리하면 수동 날짜 Param과 자동 data interval 중 무엇을
우선해야 하는지 모호해지지 않습니다.

### 일일 schedule

- `CronDataIntervalTimetable("0 0 * * *", timezone="Asia/Seoul")`
- `catchup=False`
- `max_active_runs=1`
- 처음 등록될 때는 pause 상태

자정에 끝난 하루 구간을 처리하며, missed interval은 자동으로 한꺼번에 실행하지
않습니다. 빠진 날짜는 검증된 수동 일일 DAG 또는 최대 3일 backfill DAG로 복구합니다.

### 과거 판매 날짜 매핑

배포 시 다음 설정을 코드 밖에서 주입합니다.

- simulation schedule 시작일
- 원본 판매 시작일 `2009-12-01`
- 원본 판매 종료일 `2011-12-09`

매핑 공식은 다음과 같습니다.

```text
지난 일수 = data_interval_start 날짜 - simulation schedule 시작일
처리 판매 날짜 = 원본 판매 시작일 + 지난 일수
```

예를 들어 schedule 시작일이 `2026-08-16`이면 다음과 같이 재생됩니다.

| Airflow data interval 시작일 | 처리 판매 날짜 |
|---|---|
| 2026-08-16 | 2009-12-01 |
| 2026-08-17 | 2009-12-02 |
| 2026-08-18 | 2009-12-03 |

원본 종료일을 넘으면 빈 배치를 성공 처리하지 않고 명확하게 중단하거나 skip하도록
구현 단계에서 계약을 테스트합니다.

## 선택 이유

- 실제 운영 pipeline처럼 “완료된 하루 구간”을 다음 자정에 처리할 수 있습니다.
- 2009년 원본을 수정하지 않고 현재 시간에 맞춰 순차적으로 재생할 수 있습니다.
- 수동 재처리와 자동 일일 실행의 날짜 해석이 섞이지 않습니다.
- `catchup=False`와 최초 pause로 과거 전체 기간의 우발 실행을 막습니다.

## 감수하는 제한

- scheduler가 멈춘 날짜는 자동으로 모두 복구되지 않으므로 backfill이 필요합니다.
- simulation 기준일 설정이 바뀌면 같은 Airflow 날짜가 다른 판매 날짜로 연결될 수
  있어, 실행 시작 후에는 설정을 임의로 변경하면 안 됩니다.
- 실제 실시간 판매 데이터가 연결되면 과거 날짜 offset 매핑은 제거해야 합니다.

## 공식 참고 자료

- [Airflow DAG Run과 Data Interval](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html)
- [Airflow Template Context 날짜](https://airflow.apache.org/docs/apache-airflow/stable/templates-ref.html)
- [CronDataIntervalTimetable API](https://airflow.apache.org/docs/apache-airflow/stable/_api/airflow/timetables/interval/index.html)
- [Airflow 3 schedule 변경 사항](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)
