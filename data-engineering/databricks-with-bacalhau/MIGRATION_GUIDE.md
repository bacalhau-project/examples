# Autoloader Rearchitecture Guide

## Overview

This guide documents the complete rearchitecture from raw S3 uploads to Databricks Autoloader with Unity Catalog and UC Volumes. The new architecture provides better scalability, reliability, and governance while maintaining all existing functionality.

## Migration Summary

### Before (Raw S3 Uploads)
- Direct Databricks SQL connector uploads via `sqlite_to_databricks_uploader.py`
- Manual table management and schema evolution
- Limited scalability and error handling
- Basic monitoring and alerting
- Multiple execution paths and python scripts

### After (Autoloader + UC Volumes - ONLY EXECUTION METHOD)
- **Single consolidated execution**: `uv run -s autoloader_main.py`
- S3 landing service writes files for Autoloader processing
- Unity Catalog managed external locations and volumes
- Automatic schema evolution and checkpoint management
- Comprehensive monitoring and governance
- **NO alternative execution paths** - Autoloader only

## New Architecture Components

## 🚀 SINGLE EXECUTION METHOD - Autoloader Main

**All functionality is consolidated into one command:**

```bash
# Setup complete infrastructure
uv run -s autoloader_main.py setup

# Process data (replaces ALL old processing methods)  
uv run -s autoloader_main.py process --db-path sensor_data.db

# Continuous processing
uv run -s autoloader_main.py process --continuous --interval 60

# Start monitoring dashboard
uv run -s autoloader_main.py monitor

# Run all tests
uv run -s autoloader_main.py test

# Check system status
uv run -s autoloader_main.py status
```

### 1. Unity Catalog Infrastructure (Integrated)
```bash
# Setup UC infrastructure (part of main setup)
uv run -s autoloader_main.py setup
```

**Features:**
- Creates storage credentials with IAM role integration
- Sets up external locations for all S3 buckets
- Creates UC Volumes for checkpoint and schema storage
- Configures permissions for teams and service principals
- Validates S3 access and connectivity

### 2. Data Processing (Consolidated)
```bash
# Process data once (replaces sqlite_to_databricks_uploader.py)
uv run -s autoloader_main.py process --db-path sensor_data.db

# Continuous processing (replaces all pipeline scripts)
uv run -s autoloader_main.py process --continuous --interval 60
```

**Features:**
- **ONLY** way to process data - no alternatives
- Replaces ALL previous upload/processing scripts
- Writes JSON files to S3 for Autoloader processing
- Maintains existing validation and routing logic
- Supports all pipeline types (raw, schematized, filtered, emergency)
- Includes date-based partitioning and metadata

### 3. Monitoring Dashboard (Integrated)
```bash
# Start monitoring dashboard
uv run -s autoloader_main.py monitor
```

**Features:**
- S3 landing zone metrics and file tracking
- Autoloader table status and ingestion monitoring
- Pipeline processing statistics and health checks
- Real-time dashboard with auto-refresh
- Detailed bucket and file analysis

### 4. Testing Framework (Integrated)
```bash
# Run all tests
uv run -s autoloader_main.py test

# Run specific tests
uv run -s autoloader_main.py test --type emergency
```

**Features:**
- Mock S3 services for local testing
- Validates all pipeline types and data flows
- Tests emergency detection and routing
- Verifies S3 access and data partitioning
- Comprehensive test coverage for migration

## Configuration Files

### Unity Catalog Configuration (`unity_catalog_config.yaml`)
```yaml
databricks:
  hostname: "your-workspace.databricks.com"
  http_path: "/sql/1.0/endpoints/your-endpoint"
  token: "${DATABRICKS_TOKEN}"

external_locations:
  - name: "sensor_data_raw_location"
    s3_path: "s3://sensor-data-raw-us-east-1/"
  - name: "sensor_data_schematized_location"
    s3_path: "s3://sensor-data-schematized-us-east-1/"
  # ... more locations

uc_volumes:
  - name: "autoloader_checkpoints"
    catalog: "sensor_data_catalog"
    schema: "sensor_pipeline"
    external_location: "autoloader_checkpoints_location"
  # ... more volumes
```

### Environment Variables
```bash
# Required for setup
export DATABRICKS_HOST="your-workspace.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/endpoints/your-endpoint"
export DATABRICKS_TOKEN="your-databricks-token"
export AWS_REGION="us-east-1"
export DATABRICKS_IAM_ROLE="arn:aws:iam::123456789012:role/databricks-unity-catalog-role"

# S3 bucket configuration
export S3_BUCKET_RAW="sensor-data-raw-us-east-1"
export S3_BUCKET_SCHEMATIZED="sensor-data-schematized-us-east-1"
export S3_BUCKET_FILTERED="sensor-data-filtered-us-east-1"
export S3_BUCKET_EMERGENCY="sensor-data-emergency-us-east-1"
export S3_BUCKET_CHECKPOINTS="sensor-data-checkpoints-us-east-1"
```

## Deployment Process - SINGLE COMMAND APPROACH

### 1. Complete Setup (One Command)
```bash
# Setup everything - infrastructure, pipelines, validation
uv run -s autoloader_main.py setup
```

### 2. Start Processing (One Command)
```bash
# Process data once
uv run -s autoloader_main.py process --db-path sensor_data.db

# OR continuous processing
uv run -s autoloader_main.py process --continuous --interval 60
```

### 3. Start Monitoring (One Command)  
```bash
# Start monitoring dashboard
uv run -s autoloader_main.py monitor
```

**Access Points:**
- Dashboard: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 4. Check Status (One Command)
```bash
# Check everything is working
uv run -s autoloader_main.py status
```

### 5. Run Tests (One Command)
```bash
# Test complete workflow
uv run -s autoloader_main.py test
```

**NO manual step-by-step setup needed** - everything is consolidated!

## Migration Benefits

### Scalability Improvements
- **Automatic Scaling**: Autoloader scales based on data volume
- **Parallel Processing**: Multiple streams can process data simultaneously
- **Cost Optimization**: Pay only for data processed, not idle time

### Reliability Enhancements
- **Built-in Retry Logic**: Automatic retry for transient failures
- **Checkpoint Management**: Exactly-once processing guarantees
- **Schema Evolution**: Handle schema changes without downtime
- **Error Isolation**: Invalid data doesn't block processing

### Governance and Security
- **Unity Catalog Integration**: Centralized data governance
- **Fine-grained Permissions**: Row and column-level security
- **Audit Logging**: Complete audit trail of data access
- **Data Lineage**: Track data from source to destination

### Operational Benefits
- **Monitoring**: Rich metrics and alerting capabilities
- **Debugging**: Better error reporting and troubleshooting
- **Maintenance**: Reduced operational overhead
- **Compliance**: Built-in compliance and governance features

## Testing and Validation

### Local Testing (Consolidated)
```bash
# Run all tests locally with mock services
uv run -s autoloader_main.py test

# Test specific components
uv run -s autoloader_main.py test --type raw          # Test raw pipeline
uv run -s autoloader_main.py test --type schematized  # Test validation
uv run -s autoloader_main.py test --type emergency    # Test emergency detection
uv run -s autoloader_main.py test --type s3-access    # Test S3 connectivity
```

### Production Validation (Consolidated)
```bash
# Check complete system status
uv run -s autoloader_main.py status

# Monitor processing in real-time
curl http://localhost:8000/api/health
curl http://localhost:8000/api/s3-metrics
curl http://localhost:8000/api/autoloader-tables
```

## Migration Checklist

### Pre-Migration
- [ ] Set up Unity Catalog workspace
- [ ] Configure IAM roles and permissions
- [ ] Create S3 buckets for external locations
- [ ] Set required environment variables
- [ ] Validate existing data pipeline functionality

### Migration Steps
- [ ] Run infrastructure setup script
- [ ] Validate Unity Catalog configuration
- [ ] Test S3 landing service locally
- [ ] Deploy Autoloader pipelines
- [ ] Configure monitoring dashboard
- [ ] Run comprehensive tests

### Post-Migration
- [ ] Monitor pipeline performance
- [ ] Validate data quality and completeness
- [ ] Set up alerting and notifications
- [ ] Train team on new monitoring tools
- [ ] Document operational procedures

### Rollback Plan
- [ ] Keep old pipeline code for emergency rollback
- [ ] Maintain parallel processing during transition
- [ ] Document rollback procedures
- [ ] Test rollback scenarios

## Troubleshooting

### Common Issues and Solutions

#### Unity Catalog Setup
```bash
# Issue: Storage credential creation fails
# Solution: Verify IAM role has correct permissions
aws sts assume-role --role-arn $DATABRICKS_IAM_ROLE --role-session-name test

# Issue: External location access denied
# Solution: Check S3 bucket permissions and IAM policies
python setup_unity_catalog_infrastructure.py --config unity_catalog_config.yaml --validate
```

#### Autoloader Pipeline Issues
```bash
# Issue: Schema evolution errors
# Solution: Check UC Volume permissions
python autoloader_pipeline_manager.py --config unity_catalog_config.yaml --action validate

# Issue: Checkpoint corruption
# Solution: Clear checkpoint and restart
# (This is handled automatically by UC Volumes)
```

#### S3 Landing Service
```bash
# Issue: S3 upload failures
# Solution: Validate S3 access and credentials
python s3_autoloader_landing_service.py --validate-access

# Issue: Data not appearing in Autoloader
# Solution: Check file format and partitioning
curl http://localhost:8000/api/bucket-details/raw
```

## Performance Tuning

### Autoloader Optimization
- Configure appropriate trigger intervals
- Optimize checkpoint cleanup policies
- Tune schema inference settings
- Set up appropriate partitioning strategies

### S3 Landing Service
- Adjust batch sizes based on data volume
- Configure appropriate upload intervals
- Optimize JSON file sizes for processing
- Use proper S3 storage classes

### Monitoring and Alerting
- Set up CloudWatch metrics for S3
- Configure Databricks job monitoring
- Create alerts for pipeline failures
- Monitor data freshness and quality

## Support and Maintenance

### Daily Operations
- Monitor dashboard for pipeline health
- Review S3 landing service logs
- Check for schema evolution events
- Validate data quality metrics

### Weekly Tasks
- Review checkpoint storage usage
- Analyze processing performance trends
- Update data quality rules as needed
- Check for new Unity Catalog features

### Monthly Tasks
- Review and optimize costs
- Update documentation and procedures
- Train team on new features
- Plan capacity and scaling needs

---

This rearchitecture provides a robust, scalable foundation for sensor data processing with Databricks Autoloader while maintaining all existing functionality and improving operational capabilities.
