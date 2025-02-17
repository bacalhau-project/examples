-- Set partition variables from environment (with defaults)
SET VARIABLE bacalhau_partition_count = coalesce(try_cast(getenv('BACALHAU_PARTITION_COUNT') as INTEGER), 1);
SET VARIABLE bacalhau_partition_index = coalesce(try_cast(getenv('BACALHAU_PARTITION_INDEX') as INTEGER), 0);

-- Partition check helper
-- Returns true if the input value belongs to current partition
CREATE OR REPLACE MACRO belongs_to_partition(value) AS (
    md5_number_lower(value::VARCHAR) % getvariable('bacalhau_partition_count') = getvariable('bacalhau_partition_index')
);

-- Hash-based partitioning
-- Partitions files based on a hash of their full path
-- Usage: SELECT * FROM partition_by_hash('/data/*.csv')
CREATE OR REPLACE MACRO partition_by_hash(pattern) AS 
    TABLE FROM (
        SELECT *
        FROM glob(pattern)
        WHERE belongs_to_partition(file)
    );

-- Regex-based partitioning
-- Partitions files based on a regex pattern match
-- Parameters:
--   pattern: glob pattern for files
--   regex: regex pattern with capture groups
--   group_num: which capture group to use for partitioning (default: 1)
CREATE OR REPLACE MACRO partition_by_regex(
    pattern, 
    regex, 
    group_num := 1
) AS
    TABLE FROM (
        SELECT 
            file,
            regexp_extract(file, regex, group_num) as matched_part
        FROM glob(pattern)
        WHERE belongs_to_partition(regexp_extract(file, regex, group_num))
    );

-- Date-based partitioning
-- Partitions files based on dates found in filenames
-- Parameters:
--   pattern: glob pattern for files
--   date_regex: regex pattern with capture groups for year, month, day
--   part: date part to group by (default: day)
-- 
-- Common patterns:
--   - data_YYYYMMDD.csv:    data_(\d{4})(\d{1,2})(\d{2})\.csv
--   - YYYY/MM/DD/*.log:     (\d{4})/(\d{1,2})/(\d{2})
--   - YYYY-MM-DD-data.csv:  (\d{4})-(\d{1,2})-(\d{2})
--   - data.YYYYMMDD:        \.(\d{4})(\d{1,2})(\d{2})$
CREATE OR REPLACE MACRO partition_by_date(
    pattern,
    date_regex,  
    part := 'day'
) AS 
    TABLE FROM (
        WITH parsed_dates AS (
            SELECT file,
                   regexp_extract(file, date_regex, ['year', 'month', 'day']) as date_parts,
                   try_cast(strptime(
                       date_parts['year'] || '-' || 
                       lpad(date_parts['month'], 2, '0') || '-' || 
                       date_parts['day'], 
                       '%Y-%m-%d'
                   ) as date) as extracted_date
            FROM glob(pattern)
            WHERE regexp_matches(file, date_regex)
              AND extracted_date IS NOT NULL
        )
        SELECT 
            file,
            extracted_date,
            date_trunc(part, extracted_date) as partition_date
        FROM parsed_dates
        WHERE belongs_to_partition(partition_date)
    );