-- 원본에 가까운 판매 데이터를 후속 가공 테이블과 분리해 보존한다.
CREATE SCHEMA IF NOT EXISTS raw;

-- 파일 체크섬과 CSV 행 번호를 키로 사용해 같은 파일의 재적재를 중복 없이 처리한다.
CREATE TABLE IF NOT EXISTS raw.retail_sales (
    source_file_sha256 character(64) NOT NULL,
    source_row_number bigint NOT NULL,
    invoice_id text NOT NULL,
    stock_code text NOT NULL,
    description text,
    quantity integer NOT NULL,
    invoice_datetime timestamp without time zone NOT NULL,
    sale_date date NOT NULL,
    unit_price numeric(18, 6) NOT NULL,
    customer_id text,
    country text NOT NULL,
    is_customer_identified boolean NOT NULL,
    is_cancellation boolean NOT NULL,
    is_return boolean NOT NULL,
    is_zero_price boolean NOT NULL,
    is_negative_price boolean NOT NULL,
    ingested_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_file_sha256, source_row_number),
    CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (source_row_number > 0),
    CHECK (sale_date = invoice_datetime::date),
    CHECK (is_customer_identified = (customer_id IS NOT NULL)),
    CHECK (is_cancellation = (upper(invoice_id) LIKE 'C%')),
    CHECK (is_return = (quantity < 0)),
    CHECK (is_zero_price = (unit_price = 0)),
    CHECK (is_negative_price = (unit_price < 0))
);

-- 날짜별 simulator 배치와 주문·고객 조회에 필요한 최소 인덱스만 만든다.
CREATE INDEX IF NOT EXISTS retail_sales_sale_date_idx
    ON raw.retail_sales (sale_date);
CREATE INDEX IF NOT EXISTS retail_sales_invoice_id_idx
    ON raw.retail_sales (invoice_id);
CREATE INDEX IF NOT EXISTS retail_sales_customer_id_idx
    ON raw.retail_sales (customer_id)
    WHERE customer_id IS NOT NULL;
