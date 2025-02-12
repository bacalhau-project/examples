# DuckDB Container for Bacalhau Distributed Processing

This container bridges the gap between DuckDB (a single-instance database) and Bacalhau's distributed computing capabilities, enabling parallel SQL query processing across multiple nodes.

## The Problem

DuckDB is a powerful analytical database, but it's designed to run on a single instance. When processing large datasets, you need:

- A way to split data processing across multiple machines
- Coordination between processing nodes
- Efficient data partitioning strategies

## The Solution

This container provides SQL functions that automatically work with Bacalhau's partitioning feature to:

1. Split data processing across nodes using various partitioning strategies
2. Handle partition assignment automatically
3. Enable consistent data processing across nodes

## Partitioning Functions

We've introduced several User-Defined Functions (UDFs) to handle data partitioning in DuckDB:

### 1. Hash-Based Partitioning

```sql
-- Automatically partitions data based on file path hash
SET VARIABLE my_files = (
    SELECT LIST(file) FROM partition_by_hash('s3://bucket/*.parquet')
);

-- Use the variable in your query
SELECT * FROM read_parquet(getvariable('my_files'));
```

### 2. Regex-Based Partitioning

```sql
-- Partitions files based on regex pattern matches
SET VARIABLE my_files = (
    SELECT LIST(file) FROM partition_by_regex(
        's3://bucket/data_*.parquet',  -- file pattern
        'data_([A-Z]).*'              -- regex with capture group
    )
);

SELECT * FROM read_parquet(getvariable('my_files'));
```

### 3. Date-Based Partitioning

```sql
-- Partitions by dates in filenames
SET VARIABLE my_files = (
    SELECT LIST(file) FROM partition_by_date(
        's3://bucket/logs/*.parquet',           -- file pattern
        'logs_(\d{4})(\d{2})(\d{2})\.parquet', -- date regex
        'month'                                 -- partition by month
    )
);

SELECT * FROM read_parquet(getvariable('my_files'));
```

## Common Patterns

1. **Variable Setting**

```sql
-- Always set variables first, then use them
SET VARIABLE my_files = (SELECT LIST(file) FROM partition_by_hash('pattern'));
SELECT * FROM read_parquet(getvariable('my_files'));
```

2. **Partition Count**

```bash
# Match partition count to data volume and processing needs
bacalhau docker run --count 3 ...
```

## Usage Examples

### 1. Basic Usage

```bash
bacalhau docker run \
  ghcr.io/bacalhau-project/duckdb \
  "SELECT 'Hello Bacalhau!' as greeting;"
```

### 2. Processing Log Files

```bash
bacalhau docker run \
  --count 3 \
  ghcr.io/bacalhau-project/duckdb \
  "
  -- Get files for this partition
  SET VARIABLE my_logs = (
    SELECT LIST(file) FROM partition_by_date(
      's3://my-bucket/logs/*.parquet',
      'logs_(\d{4})(\d{2})(\d{2})\.parquet',
      'month'
    )
  );

  -- Process assigned files
  SELECT * FROM read_parquet(getvariable('my_logs'));
  "
```

### 3. Distributed Data Processing

```bash
bacalhau docker run \
  --count 3 \
  ghcr.io/bacalhau-project/duckdb \
  "
  -- Get files for this partition
  SET VARIABLE user_files = (
    SELECT LIST(file) FROM partition_by_hash('s3://bucket1/users/*.parquet')
  );

  -- Process user data
  SELECT
    name,
    email,
    signup_date
  FROM read_parquet(getvariable('user_files'));
  "
```

### 4. Pattern-Based File Processing

```bash
bacalhau docker run \
  --count 4 \
  ghcr.io/bacalhau-project/duckdb \
  "
  -- Get files matching pattern for this partition
  SET VARIABLE region_files = (
    SELECT LIST(file) FROM partition_by_regex(
      's3://bucket/region_*.parquet',
      'region_([A-Z]{2})_.*'  -- e.g., region_US_data.parquet
    )
  );

  -- Process regional data
  SELECT * FROM read_parquet(getvariable('region_files'));
  "
```

## How It Works

1. **Automatic Partition Detection**

   - Bacalhau handles partition creation and distribution
   - When you specify `--count N`, Bacalhau:
     - Creates N partitions (0 to N-1)
     - Assigns each partition to available compute nodes
     - Provides partition information via environment variables
   - Our SQL functions automatically detect and use this information

2. **Partitioning Strategies**

   - When Bacalhau executes your query across nodes:
     - `partition_by_hash`: Evenly distributes files using path hash
     - `partition_by_regex`: Groups files by pattern matches
     - `partition_by_date`: Splits files by time periods
   - Each node processes only its assigned partition

3. **Direct Data Access**
   - DuckDB handles data reading from:
     - S3 buckets
     - HTTP/HTTPS sources
     - Local files
   - Bacalhau manages:
     - Node distribution
     - Execution tracking
     - Error handling and retries
     - Result collection

## Building and Testing

```bash
make build
make test
```

## Support

For issues and feature requests, please use the GitHub issue tracker.
