-- ============================================================================
-- Lab 8 (Part 4): Зовнішня таблиця Athena для потокових мікро-батчів у S3
-- S3 Location: s3://onetwothree-analytics-2surf/stream-data/
-- ============================================================================

CREATE EXTERNAL TABLE IF NOT EXISTS streamed_payments (
    invoiceId       STRING,
    amount          BIGINT,
    ccy             INT,
    reference       STRING,
    createdDate     STRING,
    merchantId      STRING,
    merchantName    STRING,
    mcc             INT,
    customerId      STRING,
    paymentMethod   STRING,
    device          STRING,
    status          STRING,
    modifiedDate    STRING,
    finalAmount     BIGINT,
    failureReason   STRING,
    receivedAt      STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'ignore.malformed.json' = 'true',
    'case.insensitive' = 'true'
)
LOCATION 's3://onetwothree-analytics-2surf/stream-data/'
TBLPROPERTIES (
    'has_encrypted_data' = 'false',
    'classification' = 'json'
);

-- ============================================================================
-- Фінальні SELECT-запити для перевірки результатів із форматуванням сум у грн
-- ============================================================================

-- 1. Перегляд доставлених потокових транзакцій із переведенням копійок у гривні
SELECT
    invoiceId,
    merchantName,
    paymentMethod,
    status,
    ROUND(amount / 100.0, 2) AS amount_uah,
    ROUND(finalAmount / 100.0, 2) AS final_amount_uah,
    ccy,
    modifiedDate,
    receivedAt,
    COALESCE(failureReason, '-') AS failure_reason
FROM streamed_payments
ORDER BY receivedAt DESC
LIMIT 25;

-- 2. Підсумкова агрегація за статусами серед 50 доставлених подій (у грн)
SELECT
    status,
    COUNT(*) AS events_count,
    COUNT(DISTINCT invoiceId) AS unique_invoices,
    ROUND(SUM(amount) / 100.0, 2) AS total_requested_uah,
    ROUND(SUM(finalAmount) / 100.0, 2) AS total_settled_uah
FROM streamed_payments
GROUP BY status
ORDER BY events_count DESC;
