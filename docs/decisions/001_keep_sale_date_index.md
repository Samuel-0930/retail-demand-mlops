# 날짜별 검증 인덱스 결정

## 배경

날짜별 검증은 `source_file_sha256`와 `sale_date`를 함께 조건으로 사용합니다.
따라서 두 컬럼을 묶은 복합 인덱스가 필요한지 실제 PostgreSQL 실행 계획으로
확인했습니다.

## 측정

2026-08-15 로컬 PostgreSQL에서 1,044,848행이 적재된 상태로
`2009-12-01`의 3,223행을 집계했습니다.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    count(*),
    min(source_row_number),
    max(source_row_number),
    count(*) FILTER (WHERE customer_id IS NULL),
    count(*) FILTER (WHERE is_cancellation),
    count(*) FILTER (WHERE is_return)
FROM raw.retail_sales
WHERE source_file_sha256 = $1
  AND sale_date = DATE '2009-12-01';
```

핵심 결과는 다음과 같습니다.

```text
Index Scan using retail_sales_sale_date_idx
actual rows=3223
shared buffers hit=95
execution time=2.014 ms
```

이 수치는 로컬 캐시와 장비 상태에 따라 달라질 수 있으므로 절대적인 성능
보장값이 아니라 현재 인덱스 선택이 적절한지 판단하는 근거로만 사용합니다.

## 결정

기존 `retail_sales_sale_date_idx`를 유지하고 복합 인덱스는 추가하지 않습니다.
날짜 조건만으로 약 3천 행까지 충분히 좁혀지며, 현재 실행 시간도 짧습니다.
복합 인덱스를 추가하면 디스크 사용량과 매 적재 시 인덱스 갱신 비용이 늘어납니다.

## 재검토 조건

다음 중 하나가 발생하면 같은 쿼리를 다시 측정합니다.

- 서로 다른 원본 파일이 같은 날짜로 반복 적재되어 날짜당 행 수가 크게 증가할 때
- 날짜별 검증이 운영상 허용할 수 없을 정도로 느려질 때
- 실행 계획이 날짜 인덱스 대신 전체 테이블 순차 조회를 선택할 때

