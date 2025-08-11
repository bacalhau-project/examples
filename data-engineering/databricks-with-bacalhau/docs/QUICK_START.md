# Quick Start Guide

## Prerequisites
- AWS credentials configured
- Databricks workspace with Unity Catalog
- `.env` file with required variables (see `.env.example`)

## 1. Verify Setup
```bash
cd scripts
uv run -s verify-databricks-setup.py
```

## 2. Run Demo (No UI Required)
```bash
# Run complete demo from command line
./run-demo-headless.sh
```

This will:
- Upload and run the Auto Loader setup notebook
- Create test sensor data
- Upload data to S3
- Show query results

## 3. Manual Steps (Alternative)

### Setup Infrastructure
```bash
cd scripts
# Create external locations if needed
uv run -s setup-external-locations.py

# Verify everything is ready
uv run -s verify-databricks-setup.py
```

### Run Auto Loader
```bash
# Upload and run setup notebook
uv run -s upload-and-run-notebook.py \
  --notebook ../databricks-notebooks/01-setup-autoloader-demo.py \
  --run --wait
```

### Upload Test Data
```bash
cd ../databricks-uploader
uv run -s test-upload.py
```

### Query Results
```bash
cd ../scripts
uv run -s run-databricks-sql.py --query \
  "SELECT COUNT(*) FROM sensor_data.sensor_readings_ingestion"
```

### Teardown
```bash
# Get demo ID from setup output, then:
uv run -s upload-and-run-notebook.py \
  --notebook ../databricks-notebooks/02-teardown-autoloader-demo.py \
  --run -p demo_id=YOUR_DEMO_ID
```

## Key Scripts

### Infrastructure
- `scripts/setup-external-locations.py` - Create Unity Catalog external locations
- `scripts/verify-databricks-setup.py` - Verify all infrastructure is ready

### Execution
- `scripts/upload-and-run-notebook.py` - Upload and run any notebook
- `scripts/run-databricks-sql.py` - Execute SQL queries
- `run-demo-headless.sh` - Complete demo runner

### Notebooks
- `01-setup-autoloader-demo.py` - Creates tables and Auto Loader streams
- `02-teardown-autoloader-demo.py` - Cleans up demo resources
- `03-scheduled-autoloader-processor.py` - For scheduled processing

## Troubleshooting

### AWS Token Expired
```bash
aws sso login
```

### Missing External Locations
```bash
cd scripts
uv run -s setup-external-locations.py
```

### Check Logs
```bash
# View recent ingested data
uv run -s run-databricks-sql.py --query \
  "SELECT * FROM sensor_data.sensor_readings_ingestion ORDER BY _ingested_at DESC LIMIT 10"
```