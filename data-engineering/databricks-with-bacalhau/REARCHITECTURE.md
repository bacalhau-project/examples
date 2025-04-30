## Project: Refactor Bacalhau Workflow Results to Databricks Lakehouse

**Goal:** Remove all Azure Cosmos DB sinks. Replace the existing C# Cosmos uploader with a Python-based uploader that transfers Parquet result files to Cloud Storage, and orchestrate ingestion and analytics entirely within Databricks Lakehouse.

**Current State:**
- Raw sensor data is ingested by remote Sensor processes and staged into local SQLite databases.
- Bacalhau jobs execute on remote nodes, mounting and processing SQLite data via the C# CosmosUploader:
  - C# code reads rows from SQLite and writes JSON documents to Azure Cosmos DB.

**Target State:**
- Raw sensor data on remote nodes → Sensor → Local SQLite (Staging) → Bacalhau jobs output Parquet files.
- **NEW:** A Python uploader script runs on the remote node immediately after Bacalhau completes, uploading Parquet files to Cloud Storage (AWS S3 or Azure Data Lake Storage Gen2).
- **NEW:** Databricks Auto Loader incrementally ingests Parquet files into Delta Lake tables.
- **NEW:** All downstream analytics, transformations, and reporting are performed in Databricks using PySpark/SQL on Delta Lake.
- **NEW:** Databricks Workflows orchestrate ingestion and subsequent analytics notebooks.
- C# CosmosUploader project is removed.

---

## Phase 1: Cloud Storage & Databricks Foundation

*1.1 Cloud Storage Setup (AWS S3 or ADLS Gen2)*
- Provision storage container/bucket with a flat, sensor-centric folder layout, e.g.:
  `s3://<BUCKET>/<SENSOR_ID>/`
- Configure IAM/Access policies for remote-node uploader and Databricks read access.

*1.2 Databricks Workspace & Connectivity*
- Confirm Databricks workspace access.
- Attach instance profile or configure secret-based credentials for S3/ADLS access.
- Validate connectivity in a notebook:
  ```python
  dbutils.fs.ls("s3a://<BUCKET>/")
  spark.read.parquet("s3a://<BUCKET>/<SENSOR_ID>/").show()
  ```
- (Optional) Enable Unity Catalog and create a dedicated schema/database for Bacalhau results.

## Phase 2: Modify Bacalhau Workflow for Parquet Output

*2.1 Analyze existing Bacalhau processing output schema.*
- Understand the fields, types, and any nested structures.

*2.2 Emit Parquet files from Bacalhau jobs.*
- Select Parquet as the analytics-optimized, splittable format.
- Write results to a predictable local path:
  `/var/data/<SENSOR_ID>/results_<timestamp>.parquet`.

*2.3 Remove all CosmosUploader/C# code.*
- Delete the `cosmos-uploader/` project directory.
- Clean up references in build scripts and documentation.

## Phase 3: Python Uploader Script

*3.1 Design and implement a Python uploader:*
- CLI parameters: `--input-dir`, `--cloud-bucket`, `--prefix`, `--region` or storage account details.
- Use `boto3` for S3 or `azure-storage-blob` for ADLS Gen2.

*3.2 Upload resilience:*
- Automatic retries with exponential backoff.
- Verify checksum or file size post-upload.
- On success, optionally delete or archive local Parquet file.

*3.3 Logging and monitoring:*
- Emit logs to stdout/stderr in JSON or plain text.
- Integrate with remote-node monitoring/alerting.

## Phase 4: Databricks Data Ingestion

*4.1 Define Delta Lake table schema:*
- Mirror Parquet schema; plan for schema evolution.

*4.2 Implement incremental ingestion via Auto Loader:*
```python
df = (spark.readStream
      .format("cloudFiles")
      .option("cloudFiles.format", "parquet")
      .option("cloudFiles.schemaLocation", "s3a://<BUCKET>/_schemas/")
      .load("s3a://<BUCKET>/"))
df.writeStream.format("delta") \
  .option("checkpointLocation", "s3a://<BUCKET>/_checkpoints/") \
  .toTable("bacalhau_results")
```

*4.3 Initial load:*
- One-time batch `spark.read.parquet("s3a://<BUCKET>/")` if historical files exist.

## Phase 5: Analytics & Workflows

*5.1 Develop PySpark/SQL notebooks for analysis, aggregations, machine learning.*
*5.2 Create Databricks Workflows:*
- Task1: Auto Loader ingestion (streaming or scheduled).
- Task2+: Analysis notebooks, dependencies based on ingestion.
*5.3 Schedule and configure alerts on failures and performance issues.*

## Phase 6: Testing & Validation

*6.1 Local end-to-end tests:*
- Run Bacalhau job → Parquet output → Python uploader → verify in S3.
- Trigger Databricks ingestion → verify delta table contents.

*6.2 Data quality checks and monitoring.*

## Phase 7: Cleanup & Production Readiness

*7.1 Remove C# CosmosUploader artifacts and dependencies.*
*7.2 Update documentation and READMEs to reference Python uploader and Databricks.*
*7.3 Secure credentials with Databricks Secrets; manage Python script credentials via environment variables or AWS IAM roles.*
*7.4 Optimize Delta Lake tables (`OPTIMIZE`, `ZORDER`).*
*7.5 Document the full architecture, upload script usage, and Databricks workflow.*
