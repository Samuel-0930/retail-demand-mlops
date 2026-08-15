# Week 2 Airflow 계획

Week 2는 Week 1의 Python pipeline을 수정하는 단계가 아니라, Airflow가 안전하게
호출하고 실행 상태를 보여주도록 연결하는 단계입니다.

## 작업 순서

1. [완료] Airflow 3.3.0 전용 가상환경과 고정 constraints 설치 절차 추가
2. [완료] `airflow.sdk` 기반 수동 날짜 DAG 한 개 작성
3. [완료] DAG import 오류와 task 의존성 자동 테스트
4. [완료] `2009-12-01` 수동 실행과 PostgreSQL 결과 확인
5. [완료] 같은 날짜 재실행으로 멱등성 확인
6. [완료] 작은 날짜 범위 backfill 방법 결정
7. [완료] 최대 3일 순차 backfill DAG 구현과 검증
8. [완료] 일일 schedule과 data interval 매핑 결정
9. [완료] 시뮬레이션 설정과 자동 일일 DAG 구현·검증
10. [다음] Week 2 운영 Runbook과 GitHub CI 분리 여부 정리

## 단계별 원칙

- 한 단계마다 테스트 후 다음 단계로 이동합니다.
- DAG 파일에는 orchestration만 두고 적재 로직을 복사하지 않습니다.
- Airflow가 없는 기본 개발 환경과 CI를 깨뜨리지 않습니다.
- 전체 과거 데이터 catchup은 명시적으로 검증하기 전까지 활성화하지 않습니다.
- Airflow connection이나 비밀번호를 Git에 저장하지 않습니다.

## 현재 위치

세 기준 날짜를 환경 설정으로 분리하고, 명시적인 일일 data interval timetable을
사용하는 `retail_daily_simulation` DAG를 구현했습니다. DAG는 최초 pause 상태이며
`2026-08-16` 구간을 `2009-12-01` 판매 날짜로 연결하는 것을 검증했습니다. 다음
작업은 Week 2 전체 실행·복구 절차와 Airflow 전용 CI 범위를 정리하는 것입니다.
