-- 배치 실행 상태를 원본 판매 테이블과 분리해 운영 메타데이터로 관리한다.
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.ingestion_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_sha256 character(64) NOT NULL,
    batch_date date,
    status text NOT NULL,
    input_rows bigint,
    inserted_rows bigint,
    skipped_rows bigint,
    error_message text,
    started_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamp with time zone,
    CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (status IN ('running', 'succeeded', 'failed')),
    CHECK (
        (status = 'running'
            AND finished_at IS NULL
            AND input_rows IS NULL
            AND inserted_rows IS NULL
            AND skipped_rows IS NULL
            AND error_message IS NULL)
        OR
        (status = 'succeeded'
            AND finished_at IS NOT NULL
            AND input_rows IS NOT NULL
            AND inserted_rows IS NOT NULL
            AND skipped_rows IS NOT NULL
            AND input_rows >= 0
            AND inserted_rows >= 0
            AND skipped_rows >= 0
            AND input_rows = inserted_rows + skipped_rows
            AND error_message IS NULL)
        OR
        (status = 'failed'
            AND finished_at IS NOT NULL
            AND input_rows IS NULL
            AND inserted_rows IS NULL
            AND skipped_rows IS NULL
            AND error_message IS NOT NULL)
    )
);

-- 특정 날짜의 최근 실행과 실패 상태를 빠르게 확인하기 위한 운영 인덱스다.
CREATE INDEX IF NOT EXISTS ingestion_runs_batch_date_started_at_idx
    ON ops.ingestion_runs (batch_date, started_at DESC);
CREATE INDEX IF NOT EXISTS ingestion_runs_status_idx
    ON ops.ingestion_runs (status);
