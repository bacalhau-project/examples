-- Session-level optimizations
SET statement_timeout = 120000;  -- 2 minutes
SET synchronous_commit = OFF;
SET work_mem = '128MB';
SET maintenance_work_mem = '256MB';
SET effective_io_concurrency = 200;
SET random_page_cost = 1.1;

-- Table structure optimizations
CREATE SCHEMA IF NOT EXISTS log_analytics;

-- Create unlogged table for better performance

CREATE UNLOGGED TABLE IF NOT EXISTS log_analytics.raw_logs_unlogged (
    raw_line TEXT,
    upload_time TIMESTAMP WITH TIME ZONE
);
