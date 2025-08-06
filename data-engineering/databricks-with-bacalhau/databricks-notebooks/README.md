# Databricks Auto Loader Demo Notebooks

This directory contains three notebooks for demonstrating Auto Loader with S3 integration:

## Notebooks

### 1. `01-setup-autoloader-demo.py`
Sets up the Auto Loader demo pipeline with:
- Automatic 24-hour shutdown to prevent runaway costs
- S3 bucket verification
- Table creation with proper schemas
- Auto Loader stream configuration
- Cost monitoring dashboard

### 2. `02-teardown-autoloader-demo.py`
Safely tears down demo resources:
- Stops all active streams
- Deletes demo data (preserves table structure)
- Cleans up checkpoint locations
- Removes demo metadata
- Provides cost summary

### 3. `03-scheduled-autoloader-processor.py`
Lightweight scheduled processor:
- Designed to run every 5-10 minutes
- Checks demo expiration before processing
- Processes new files from S3
- Updates monitoring dashboard

## Usage

1. **Import notebooks into Databricks**:
   - Use Databricks UI to import these `.py` files as notebooks
   - They will automatically be recognized as Databricks notebooks

2. **Run setup notebook**:
   - Execute `01-setup-autoloader-demo.py`
   - Note the demo_id in the output
   - Monitor the cost dashboard

3. **Schedule processor** (optional):
   - Create a Databricks job to run `03-scheduled-autoloader-processor.py`
   - Pass the demo_id as a parameter
   - Schedule for every 5-10 minutes

4. **Clean up**:
   - Run `02-teardown-autoloader-demo.py`
   - Either specify a demo_id or clean all expired demos
   - Verify cleanup in the summary

## Configuration

All notebooks use these settings:
- **Catalog**: `expanso_databricks_workspace`
- **Database**: `sensor_data`
- **Region**: `us-west-2`
- **S3 Buckets**:
  - Ingestion: `expanso-databricks-ingestion-us-west-2`
  - Validated: `expanso-databricks-validated-us-west-2`
  - Enriched: `expanso-databricks-enriched-us-west-2`
  - Aggregated: `expanso-databricks-aggregated-us-west-2`
  - Checkpoints: `expanso-databricks-checkpoints-us-west-2`
  - Metadata: `expanso-databricks-metadata-us-west-2`

## Safety Features

- **Auto-shutdown**: Demos automatically expire after 24 hours
- **Cost tracking**: All operations are logged with cost estimates
- **Data isolation**: Each demo uses a unique demo_id
- **Clean teardown**: Removes all resources to prevent ongoing charges