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

Each example shows both imperative (using `bacalhau docker run`) and declarative (using YAML) approaches.

### 1. Basic Usage

**Imperative:**

```bash
bacalhau docker run \
  ghcr.io/bacalhau-project/duckdb \
  "SELECT 'Hello Bacalhau!' as greeting;"
```

**Declarative:**

```yaml
# hello.yaml
Name: Hello DuckDB
Type: batch
Count: 1
Tasks:
  - Name: main
    Engine:
      Type: docker
      Params:
        Image: ghcr.io/bacalhau-project/duckdb
        Parameters:
          - -c
          - "SELECT 'Hello Bacalhau!' as greeting;"
```

### 2. Processing Log Files

**Imperative:**

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

**Declarative:**

```yaml
# process-logs.yaml
Name: Process Logs
Type: batch
Count: 3
Tasks:
  - Name: main
    Engine:
      Type: docker
      Params:
        Image: ghcr.io/bacalhau-project/duckdb
        Parameters:
          - -c
          - >
            SET VARIABLE my_logs = (
              SELECT LIST(file) FROM partition_by_date(
                's3://my-bucket/logs/*.parquet',
                'logs_(\d{4})(\d{2})(\d{2})\.parquet',
                'month'
              )
            );
            SELECT * FROM read_parquet(getvariable('my_logs'));
```

### 3. Distributed Data Processing

**Imperative:**

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

**Declarative:**

```yaml
# process-users.yaml
Name: Process Users
Type: batch
Count: 3
Tasks:
  - Name: main
    Engine:
      Type: docker
      Params:
        Image: ghcr.io/bacalhau-project/duckdb
        Parameters:
          - -c
          - >
            SET VARIABLE user_files = (
              SELECT LIST(file) FROM partition_by_hash('s3://bucket1/users/*.parquet')
            );
            SELECT
              name,
              email,
              signup_date
            FROM read_parquet(getvariable('user_files'));
```

### 4. Pattern-Based File Processing

**Imperative:**

```bash
bacalhau docker run \
  --count 4 \
  ghcr.io/bacalhau-project/duckdb \
  "
  -- Get files matching pattern for this partition
  SET VARIABLE region_files = (
    SELECT LIST(file) FROM partition_by_regex(
      's3://bucket/region_*.parquet',
      'region_([A-Z]{2})_.*'
    )
  );
  SELECT * FROM read_parquet(getvariable('region_files'));
  "
```

**Declarative:**

```yaml
# process-regions.yaml
Name: Process Regions
Type: batch
Count: 4
Tasks:
  - Name: main
    Engine:
      Type: docker
      Params:
        Image: ghcr.io/bacalhau-project/duckdb
        Parameters:
          - -c
          - >
            SET VARIABLE region_files = (
              SELECT LIST(file) FROM partition_by_regex(
                's3://bucket/region_*.parquet',
                'region_([A-Z]{2})_.*'
              )
            );
            SELECT * FROM read_parquet(getvariable('region_files'));
```

Run any of the YAML examples using:

```bash
bacalhau job run example.yaml
```

### 5. Running Queries from Files

This example shows how to execute a SQL query stored in a file, using Bacalhau's input sources to make the query file available to the job.

First, create your SQL query file:

```sql
-- analytics.sql
SET VARIABLE user_files = (
  SELECT LIST(file) FROM partition_by_hash('s3://bucket1/users/*.parquet')
);

SELECT 
  DATE_TRUNC('month', signup_date) as month,
  COUNT(*) as new_users,
  AVG(age) as avg_age
FROM read_parquet(getvariable('user_files'))
GROUP BY DATE_TRUNC('month', signup_date)
ORDER BY month DESC;
```

**Imperative:**
```bash
bacalhau docker run \
  --count 3 \
  --input source=s3://my-bucket/queries/analytics.sql,dest=/query.sql \
  ghcr.io/bacalhau-project/duckdb \
  -c /query.sql
```

**Declarative:**
```yaml
# run-query-file.yaml
Name: Run Analytics Query
Type: batch
Count: 3
Tasks:
  - Name: main
    Engine:
      Type: docker
      Params:
        Image: ghcr.io/bacalhau-project/duckdb
        Parameters:
          - -c
          - /query.sql
    Inputs:
      - Target: /query.sql
        Source:
          Type: s3
          Params:
            Bucket: my-bucket
            Key: queries/analytics.sql
```

Run the YAML job:
```bash
bacalhau job run run-query-file.yaml
```

This approach is useful when:
- You have complex queries that are better maintained in separate files
- You want to version control your queries
- You need to share queries across different jobs
- You want to parameterize queries using environment variables

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
