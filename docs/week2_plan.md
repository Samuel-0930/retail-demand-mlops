# Week 2 Airflow 계획

Week 2는 Week 1의 Python pipeline을 수정하는 단계가 아니라, Airflow가 안전하게
호출하고 실행 상태를 보여주도록 연결하는 단계입니다.

## 작업 순서

1. [완료] Airflow 3.3.0 전용 가상환경과 고정 constraints 설치 절차 추가
2. [완료] `airflow.sdk` 기반 수동 날짜 DAG 한 개 작성
3. [완료] DAG import 오류와 task 의존성 자동 테스트
4. [완료] `2009-12-01` 수동 실행과 PostgreSQL 결과 확인
5. [완료] 같은 날짜 재실행으로 멱등성 확인
6. [다음] 작은 날짜 범위 backfill 방법 결정
7. 일일 schedule과 data interval 매핑 결정
8. Week 2 운영 Runbook과 GitHub CI 분리 여부 정리

## 단계별 원칙

- 한 단계마다 테스트 후 다음 단계로 이동합니다.
- DAG 파일에는 orchestration만 두고 적재 로직을 복사하지 않습니다.
- Airflow가 없는 기본 개발 환경과 CI를 깨뜨리지 않습니다.
- 전체 과거 데이터 catchup은 명시적으로 검증하기 전까지 활성화하지 않습니다.
- Airflow connection이나 비밀번호를 Git에 저장하지 않습니다.

## 현재 위치

첫 DAG에 `2009-12-01`을 연속 두 번 전달해 두 실행이 모두 성공하고, PostgreSQL의
3,223행이 늘어나지 않는 것을 확인했습니다. 다음 작업은 여러 날짜를 처리할 때 기존
backfill pipeline을 Airflow가 어떤 단위로 호출할지 작은 범위부터 결정하는 것입니다.
