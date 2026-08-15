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
10. [완료] Week 2 운영 Runbook과 Airflow 전용 CI 분리

## 단계별 원칙

- 한 단계마다 테스트 후 다음 단계로 이동합니다.
- DAG 파일에는 orchestration만 두고 적재 로직을 복사하지 않습니다.
- Airflow가 없는 기본 개발 환경과 CI를 깨뜨리지 않습니다.
- 전체 과거 데이터 catchup은 명시적으로 검증하기 전까지 활성화하지 않습니다.
- Airflow connection이나 비밀번호를 Git에 저장하지 않습니다.

## 현재 위치

Week 2의 수동 일일 실행, 최대 3일 backfill, 자동 일일 날짜 매핑, pause 상태 등록,
운영·복구 Runbook과 Airflow 전용 CI 분리까지 완료했습니다. 자동 DAG unpause와
상시 scheduler 실행은 로컬 데이터베이스와 실행 시점을 사람이 최종 확인한 뒤
수행하는 운영 작업으로 남겨둡니다.
