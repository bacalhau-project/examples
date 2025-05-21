# Migration Checklist: CosmosDB → Databricks/Delta Lake

Use this checklist to track progress. Check each box as you complete the task.

---

## 1. Cleanup & Deprecation
- [X] Archive or delete the old CosmosDB/C# uploader
  - [X] Moved `example-cosmos-with-bacalhau/` to `legacy/cosmos-uploader/` (to be removed entirely in Finalization phase)
  - [X] Remove C# build scripts (`start-cosmos-uploader.sh`, `cosmos-uploader/build.sh`, etc.)  
- [X] Archived all scripts from `utility_scripts/` to `legacy/utility_scripts/`. The `utility_scripts/` directory is now empty and can be removed or repurposed. (Original scripts included: `bulk_delete_cosmos.py`, `distribute_credentials.sh`, `enable_db_access.py`, `force_clean_bacalhau_data.py`, `list_azure_resources.py`, `postgres_optimizations.sql`, `sample_tables.sh`, `setup_log_uploader.sh`, `tune_postgres.py`, `confirm_tables.py`, `debug_postgres.py`, and its `README.md`)
- [X] Removed `rebuild_cosmos.py` and the entire `.specstory/` directory (added `.specstory/` to `.gitignore`). Original: Remove any references to CosmosDB in root‐level scripts (`rebuild_cosmos.py`, `.specstory/`, etc.)

## 2. Update Documentation
### Top-Level README.md
- [X] Rewrite introduction to describe Python uploader + Databricks architecture
- [X] Replace CosmosDB/C# instructions with S3/ADLS & Delta Lake examples  
- [X] Add usage sample: build/push container, run uploader, query Delta using Spark  

### REARCHITECTURE.md
- [ ] Update phases to reference actual paths (`uploader/`, `Dockerfile`, test scripts)
- [ ] Link to new demo-network YAML examples for Databricks uploader  

## 3. Python Uploader Enhancements (`uploader/`)  
- [x] Rename config fields for generality (e.g. `table_path` → `storage_uri`)  
- [x] Add CLI flags `--table NAME` and `--timestamp-col NAME` to override introspection  
- [ ] Document credential injection:  
  - [ ] AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`  
  - [ ] Azure: environment vars or MSI for ADLS Gen2  
- [ ] Consider chunked writes or PySpark fallback for large data volumes  
- [ ] Add basic metrics/logging endpoint or integrate Prometheus client  

## 4. Container Build & CI  
- [x] Add `.pre-commit-config.yaml` (black, isort, flake8) at repo root  
- [x] Add `GitHub Actions` workflow:  
  - [x] Run `pre-commit` checks  
  - [x] Run Python unit tests  
- Runtime image: `ghcr.io/astral-sh/uv:bookworm-slim` – script is mounted; no custom build.  
- [x] Validate Alpine runtime compatibility; if deltalake wheels fail, switch to Debian-slim base  
- [x] Removed Dockerfile and build script from uploader/  
- [x] Removed old Cosmos launcher script and YAML  
- [x] Added new Databricks uploader YAML

## 5. Testing  
### Unit Tests  
- [ ] Create `tests/` directory alongside `uploader/`  
- [ ] Test schema introspection on a small SQLite DB fixture  
- [ ] Test incremental logic: mocking `write_deltalake` to local file and verifying DataFrame contents  
- [ ] Test error conditions: missing config, no tables, no timestamp column, unreadable DB  

### Integration / Smoke Tests  
- [ ] Write a shell/Python script that:  
  1. Creates a temporary SQLite DB with known rows and timestamps  
  2. Runs the uploader container in "once" mode against `file:///tmp/delta_test`  
  3. Uses PyArrow or Delta-Standalone to verify record count in `tmp/delta_test`  
- [ ] Hook this smoke test into CI (GitHub Actions) after image build  

## 6. Bacalhau Jobs & Demo-Network  
- [ ] Create `demo-network/jobs/start_databricks_uploader.yaml` by copying `start_cosmos_uploader.yaml`  
- [ ] Update in the new YAML:  
  - `Image:` → your new Python uploader image (e.g. `ghcr.io/org/uploader:latest`)  
  - `Entrypoint:` parameters → `--config /root/uploader-config.yaml --interval 300 [--once]`  
- [ ] Rename and update scripts in `demo-network/`:  
  - `3_deploy_cosmos_uploader.sh` → `3_deploy_databricks_uploader.sh`  
  - `start-cosmos-uploader.sh` → `start-databricks-uploader.sh`  
  - Adjust file names in `1_upload_files.sh`, `2_start_sensors.sh` as needed  
- [ ] Remove or repurpose any jobs that directly edit `cosmos-config.yaml` (e.g. sanitize/schema toggles)  

## 7. Sample-Sensor & Sensor Manager  
- [ ] Ensure `pyproject.toml` lists your `sensor_manager/` package and entrypoints  
- [ ] Confirm sample-sensor writes to `/root/sensor_data.db` to match uploader mounts  
- [ ] Add a README section in `sample-sensor/` showing how to run the Python uploader container  

## 8. Credentials & Secrets  
- [ ] Document S3/ADLS credential injection:  
  - Environment variables vs. IAM roles / Azure MSI  
  - Example `uploader-config.yaml` snippet with placeholders  
- [ ] Provide guidance on storing Databricks tokens in Databricks Secrets (if using DBFS)  

## 9. Databricks Ingestion & Workflows  
- [ ] Add a sample PySpark notebook illustrating Auto Loader:  
    ```python  
    df = (spark.readStream  
          .format("cloudFiles")  
          .option("cloudFiles.format","parquet")  
          .option("cloudFiles.schemaLocation","s3a://<bucket>/_schemas/")  
          .load("s3a://<bucket>/"))  
    df.writeStream.format("delta")\\  
      .option("checkpointLocation","s3a://<bucket>/_checkpoints/")\\  
      .toTable("bacalhau_results")  
    ```  
- [ ] Document initial batch load (one-off) vs continuous streaming  
- [ ] Provide example Databricks Job/Workflow JSON or CLI commands to schedule ingestion + analysis notebooks  

## 10. Finalization & Rollout  
- [ ] Remove all residual CosmosDB/C# artifacts from repo  
- [ ] Update or remove legacy utility scripts no longer in scope  
- [ ] Announce deprecation of old pipeline to stakeholders  
- [ ] Monitor CI pipelines and dashboards for any build/test failures  
- [ ] Tag and release v1.0.0 of the new Python‐Databricks pipeline  

## Phase 1: Cloud Environment Setup

### Local Lakehouse (dev only)
- Run `docker-compose -f tools/local-lakehouse/docker-compose.yml up -d`
- Console: http://localhost:9001 (user/pass `minioadmin`)
- Point uploader at `s3://bacalhau-local/delta/<table>` with:
  ```bash
  export STORAGE_URI="s3://bacalhau-local/delta/sensor_readings"
  export AWS_ACCESS_KEY_ID=minioadmin
  export AWS_SECRET_ACCESS_KEY=minioadmin
  export AWS_REGION=us-east-1
  ```
- Spark master URL inside notebooks: `spark://spark-master:7077`

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

## Phase 3: Uploader Container

3.1 Runtime image: `ghcr.io/astral-sh/uv:bookworm-slim` – script is mounted; no custom build.

*3.2 Schema auto-detection and container invocation:*
  - The uploader script automatically detects the only user table and its timestamp column via SQLite schema introspection; no need to pass those flags.
*3.3 Container invocation pattern (continuous mode):*
  - The uploader script auto-detects the SQLite table and timestamp column via schema introspection; no need to pass those flags.
  - Create a host directory for state (last upload timestamp):
    ```bash
    mkdir -p /path/to/state
    ```
  - Run the uploader container with mounts and arguments:
    ```bash
    docker run --rm \
      -v /path/to/sensor_data.db:/data/sensor.db:ro \
      -v /path/to/state:/state \
      -e UPLOAD_INTERVAL=300 \
      uploader-image:latest \
      --sqlite /data/sensor.db \
      --table-path s3://<bucket>/<delta-table> \
      --state-dir /state \
      --interval $UPLOAD_INTERVAL
    ```
  - The container will:
    1. Read `/state/last_upload.json` to determine the last upload timestamp (initialize to epoch if missing).
    2. Query `/data/sensor.db` for new rows where `timestamp > last_upload_timestamp`.
    3. Append these new rows directly to the Delta Lake table specified by `--table-path`.
    4. Update `/state/last_upload.json` with the maximum timestamp from the uploaded batch.
    5. Sleep for `$UPLOAD_INTERVAL` seconds and repeat indefinitely.

*3.4 Remove any standalone uploader scripts; utilize the container image exclusively for uploads.*

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
- Run Bacalhau job → Parquet output → Python uploader → verify Parquet files in cloud storage (S3/ADLS).
- Trigger Databricks ingestion → verify delta table contents.

*6.2 Data quality checks and monitoring.*

## Phase 7: Cleanup & Production Readiness

*7.1 Remove C# CosmosUploader artifacts and dependencies.*
*7.2 Update documentation and READMEs to reference Python uploader and Databricks.*
*7.3 Secure credentials with Databricks Secrets; manage Python script credentials via environment variables or AWS IAM roles.*
*7.4 Optimize Delta Lake tables (`OPTIMIZE`, `ZORDER`).*
*7.5 Document the full architecture, upload script usage, and Databricks workflow.*
