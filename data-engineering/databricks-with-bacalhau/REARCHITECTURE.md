<!-- markdownlint-disable MD041 MD013 MD024 -->
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
  
- [x] Rename config fields for generality (e.g. `table_name` instead of `storage_uri`)  

- [x] Add CLI flags `--table NAME` and `--timestamp-col NAME` to override introspection  

- [ ] Document credential injection:  
  - [ ] Databricks access token configuration
  - [ ] Workspace URL and API endpoint setup

- [ ] Consider chunked writes for large data volumes  

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

- [ ] Document Databricks credential management:
  - [ ] Set up Databricks workspace
  - [ ] Configure Unity Catalog and access control
  - [ ] Set up Databricks access tokens for API access
  - [ ] Document secret management using Databricks Secrets API

## 9. Databricks Workspace Setup & Configuration

- [ ] Set up Databricks workspace:
  - [ ] Create workspace through Databricks console
  - [ ] Configure workspace settings and access control

- [ ] Configure Unity Catalog:
  - [ ] Create catalogs and schemas for data organization
  - [ ] Set up access control policies

- [ ] Set up compute resources:
  - [ ] Create compute clusters for data processing
  - [ ] Configure auto-scaling policies

- [ ] Configure networking:
  - [ ] Set up private endpoints if needed
  - [ ] Configure network access policies

- [ ] Set up monitoring and logging:
  - [ ] Configure Databricks audit logs
  - [ ] Set up monitoring and alerts
  - [ ] Configure workspace events

## 10. Data Ingestion & Workflows  

- [ ] Configure Delta Lake tables:
  - [ ] Create managed tables in Databricks
  - [ ] Set up table access controls
  - [ ] Configure table properties for optimization

- [ ] Set up ingestion workflows:
  - [ ] Create Databricks jobs for data ingestion
  - [ ] Configure job schedules and dependencies
  - [ ] Set up job monitoring and alerts

- [ ] Implement data quality checks:
  - [ ] Set up data validation rules
  - [ ] Configure data quality monitoring
  - [ ] Set up alerts for data quality issues

## 11. Finalization & Rollout  

- [ ] Remove all residual CosmosDB/C# artifacts from repo  

- [ ] Update or remove legacy utility scripts no longer in scope  

- [ ] Announce deprecation of old pipeline to stakeholders  

- [ ] Monitor CI pipelines and dashboards for any build/test failures  

- [ ] Tag and release v1.0.0 of the new Python‐Databricks pipeline  

## Phase 1: Cloud Environment Setup

### 1.1 Databricks Workspace Setup

1. Create Databricks workspace:

   ```bash
   # Using Databricks CLI
   databricks workspace create \
     --workspace-name bacalhau-databricks \
     --region <your-region>
   ```

2. Configure Unity Catalog:

   ```sql
   -- Create catalog and schema
   CREATE CATALOG IF NOT EXISTS bacalhau_catalog;
   CREATE SCHEMA IF NOT EXISTS bacalhau_catalog.sensor_data;
   ```

3. Set up compute resources:
   - Create compute cluster with appropriate instance types
   - Configure auto-scaling based on workload

4. Configure networking:
   - Set up private endpoints if needed
   - Configure network access policies

### 1.2 Network Configuration

- Configure network access policies
- Set up private endpoints if needed
- Configure workspace access controls

## Phase 2: Modify Bacalhau Workflow

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
The uploader script automatically detects the only user table and its timestamp column via SQLite schema introspection; no need to pass those flags.

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
      --table-name readings \
      --state-dir /state \
      --interval $UPLOAD_INTERVAL
    ```

  - The container will:
    1. Read `/state/last_upload.json` to determine the last upload timestamp (initialize to epoch if missing).
    2. Query `/data/sensor.db` for new rows where `timestamp > last_upload_timestamp`.
    3. Append these new rows directly to the Delta Lake table in Databricks.
    4. Update `/state/last_upload.json` with the maximum timestamp from the uploaded batch.
    5. Sleep for `$UPLOAD_INTERVAL` seconds and repeat indefinitely.

*3.4 Remove any standalone uploader scripts; utilize the container image exclusively for uploads.*

## Phase 4: Databricks Data Ingestion

### 4.1 Configure Delta Lake Tables

```sql
-- Create managed table
CREATE TABLE IF NOT EXISTS bacalhau_catalog.sensor_data.readings
USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.autoOptimize.optimizeWrite' = 'true'
);
```

### 4.2 Create Databricks Jobs

- Create job for initial data load
- Set up streaming job for continuous ingestion
- Configure job schedules and dependencies
- Set up monitoring and alerts

## Phase 5: Analytics & Workflows

*5.1 Develop PySpark/SQL notebooks for analysis, aggregations, machine learning.*

*5.2 Create Databricks Workflows:*

- Task1: Auto Loader ingestion (streaming or scheduled).
- Task2+: Analysis notebooks, dependencies based on ingestion.

*5.3 Schedule and configure alerts on failures and performance issues.*

## Phase 6: Testing & Validation

*6.1 Local end-to-end tests:*

- Run Bacalhau job → Parquet output → Python uploader → verify Delta table contents.
- Trigger Databricks ingestion → verify delta table contents.

*6.2 Data quality checks and monitoring.*

## Phase 7: Cleanup & Production Readiness

*7.1 Remove C# CosmosUploader artifacts and dependencies.*
*7.2 Update documentation and READMEs to reference Python uploader and Databricks.*
*7.3 Secure credentials with Databricks Secrets; manage Python script credentials via environment variables or AWS IAM roles.*
*7.4 Optimize Delta Lake tables (`OPTIMIZE`, `ZORDER`).*
*7.5 Document the full architecture, upload script usage, and Databricks workflow.*
