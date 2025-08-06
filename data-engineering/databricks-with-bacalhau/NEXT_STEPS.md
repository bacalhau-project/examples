# Next Steps for Pipeline v2

## What We've Completed

1. **Refactored Pipeline Architecture**
   - Moved from old scenarios (raw/schematized/filtered/emergency) to new focused scenarios
   - Created strict enum-based pipeline manager to prevent configuration errors
   - Built modular components for each processing scenario

2. **New Pipeline Scenarios**
   - **RAW**: Direct pass-through with lineage metadata
   - **SCHEMATIZED**: Validation with error bucket routing
   - **LINEAGE**: Enriches all records with execution metadata
   - **MULTI_DESTINATION**: Archives + 1-minute windowed aggregations
   - **NOTIFICATION**: SQS alerts for anomaly patterns

3. **Environment-Based Configuration**
   - Merged existing GitHub/Docker variables with pipeline variables
   - Created comprehensive environment setup scripts
   - All commands now use environment variables (no manual typing)

## Immediate Next Steps

### 1. Update Databricks Configuration

Edit `.env` and update the TODO item:
```bash
# Find your SQL endpoint path in Databricks workspace
DATABRICKS_HTTP_PATH=/sql/1.0/endpoints/your-actual-endpoint-id
```

### 2. Verify AWS Account ID

Update in `.env`:
```bash
# Get your AWS account ID
aws sts get-caller-identity --query Account --output text

# Update in .env
AWS_ACCOUNT_ID=your-actual-account-id
```

### 3. Run Initial Setup

```bash
# Load environment
source setup-environment.sh

# Create S3 buckets and Databricks configs
./start-pipeline.sh setup

# This will:
# - Create 5 S3 buckets with proper lifecycle policies
# - Generate Databricks Auto Loader configurations
# - Create IAM roles for Databricks access
# - Save all configs in databricks_autoloader_configs/
```

### 4. Configure Pipeline Scenarios

```bash
# Start with basic scenarios
./start-pipeline.sh set-scenario "raw schematized lineage"

# Test with dry run
./start-pipeline.sh dry-run

# Run live
./start-pipeline.sh run
```

### 5. Monitor Pipeline

Open three terminals:

**Terminal 1 - Pipeline Orchestrator:**
```bash
source setup-environment.sh
./pipeline_orchestrator.py
```

**Terminal 2 - Pipeline Manager:**
```bash
source setup-environment.sh
# Watch execution history
watch -n 5 "./pipeline_manager_v2.py history --limit 10"
```

**Terminal 3 - Monitoring Dashboard:**
```bash
source setup-environment.sh
./monitoring_dashboard.py
# Open http://localhost:8000
```

## Databricks Setup

1. **Configure Instance Profile**
   - Go to Databricks Admin Console → Instance Profiles
   - Add the IAM role ARN from `databricks_autoloader_configs/setup_instructions.md`

2. **Create Delta Tables**
   - Open Databricks SQL or notebook
   - Run SQL from `databricks_autoloader_configs/create_tables.sql`

3. **Start Auto Loader**
   - Create new notebook
   - Copy code from `databricks_autoloader_configs/autoloader_raw.py`
   - Run to start streaming from S3

## Testing Checklist

- [ ] Environment variables loaded successfully
- [ ] S3 buckets created
- [ ] Pipeline runs in dry mode
- [ ] Records appear in S3 buckets
- [ ] Monitoring dashboard shows data
- [ ] Databricks Auto Loader ingests data
- [ ] Delta tables populate correctly

## Remaining TODOs

1. **Update Monitoring Dashboard UI**
   - Add visualization for windowed aggregation data
   - Show anomaly notification history
   - Display pipeline scenario status

2. **Production Deployment**
   - Create Docker image with environment variables
   - Deploy to AWS Spot instances
   - Set up CloudWatch monitoring

3. **Documentation**
   - Update main README with v2 architecture
   - Create runbook for operations team
   - Document troubleshooting procedures

## Quick Reference

```bash
# Always start with
source setup-environment.sh

# Common commands
./start-pipeline.sh setup                    # One-time setup
./start-pipeline.sh set-scenario "..."       # Configure scenarios  
./start-pipeline.sh dry-run                  # Test without uploads
./start-pipeline.sh run                      # Run pipeline
./start-pipeline.sh status                   # Check status
./start-pipeline.sh monitor                  # View S3 uploads

# Direct component testing
./lineage_enricher.py                        # Test lineage
./schematization_pipeline.py                 # Test validation
./windowing_aggregator.py                    # Test aggregation
./anomaly_notifier.py                        # Test notifications
```

## Support

- Pipeline issues: Check `./pipeline_orchestrator.py` logs
- S3 issues: Verify AWS credentials with `aws sts get-caller-identity`
- Databricks issues: Check Auto Loader checkpoint location
- Environment issues: Run `source setup-environment.sh` to validate