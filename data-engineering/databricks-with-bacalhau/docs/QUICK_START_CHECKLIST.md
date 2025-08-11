# ⚡ Quick Start Checklist
## Autoloader-Only Pipeline - Step-by-Step Verification

**Copy and execute each command, verifying the expected output before proceeding.**

---

## ✅ Prerequisites Check

### 1. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
**✅ Expected:** Installation success message

### 2. Verify Directory
```bash
cd /Users/daaronch/code/bacalhau-examples/data-engineering/databricks-with-bacalhau/databricks-uploader
pwd
```
**✅ Expected:** `/Users/daaronch/code/bacalhau-examples/data-engineering/databricks-with-bacalhau/databricks-uploader`

### 3. Test uv
```bash
uv --version
```
**✅ Expected:** `uv 0.x.x` (any recent version)

---

## 🔧 Environment Setup

### 4. Set Environment Variables
```bash
# REQUIRED - Replace with your actual values
export DATABRICKS_HOST="your-workspace.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/endpoints/your-endpoint"
export DATABRICKS_TOKEN="your-databricks-token"
export AWS_REGION="us-east-1"
export DATABRICKS_IAM_ROLE="arn:aws:iam::123456789012:role/databricks-unity-catalog-role"

# OPTIONAL - Uses defaults if not set
export UC_CATALOG="sensor_data_catalog"
export UC_SCHEMA="sensor_pipeline"
```

### 5. Verify Environment
```bash
env | grep -E "(DATABRICKS|AWS|UC_)" | sort
```
**✅ Expected:** All variables listed with your values

---

## 🏗️ Infrastructure Setup

### 6. Setup Infrastructure
```bash
uv run -s autoloader_main.py setup
```
**✅ Expected:** 
- "✅ Storage credential 'sensor_pipeline_storage_cred' created"
- "✅ External location 'sensor_data_raw_location' created" (x5 locations)
- "✅ UC Volume 'autoloader_checkpoints' created" (x2 volumes)
- "✅ Autoloader table 'sensor_readings_raw' created" (x4 tables)
- "✅ Autoloader infrastructure setup completed!"

### 7. Verify Infrastructure
```bash
uv run -s autoloader_main.py status
```
**✅ Expected:**
- "🏗️ Unity Catalog Infrastructure: Tables: 4"
- "✅ sensor_readings_raw: 0 records" (x4 tables)
- "✅ S3 Access: Valid"
- "✅ Overall Status: healthy"

---

## 📊 Data Processing

### 8. Create Test Data
```bash
python create_test_sensor_data.py
ls -la sensor_data.db
```
**✅ Expected:** 
- File creation messages
- `-rw-r--r-- ... sensor_data.db` (file exists)

### 9. Verify Test Data
```bash
sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_data;"
```
**✅ Expected:** `1000` (or another number > 0)

### 10. Process Single Batch
```bash
uv run -s autoloader_main.py process --db-path sensor_data.db
```
**✅ Expected:**
- "📊 Processing data with Autoloader..."
- "📊 Processing Results:"
- "Pipeline: schematized"
- "Records: 1000"
- "Uploads: 4" with S3 URIs

### 11. Verify Processing
```bash
uv run -s autoloader_main.py status
```
**✅ Expected:**
- Tables showing > 0 records:
  - "✅ sensor_readings_raw: 1000 records"
  - "✅ sensor_readings_schematized: 850 records" (filtered count)
  - etc.

---

## 📊 Monitoring

### 12. Start Monitoring (Background)
```bash
uv run -s autoloader_main.py monitor --port 8000 &
sleep 5  # Wait for startup
```
**✅ Expected:** 
- "🚀 Dashboard starting at http://0.0.0.0:8000"
- "INFO: Uvicorn running on http://0.0.0.0:8000"

### 13. Test API Health
```bash
curl http://localhost:8000/api/health
```
**✅ Expected:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-03T...",
  "components": {
    "databricks": {"status": "connected"},
    "s3": {"status": "accessible"}
  }
}
```

### 14. Test Pipeline Status
```bash
curl http://localhost:8000/api/pipelines/status
```
**✅ Expected:** JSON with pipeline status and record counts

### 15. Stop Monitoring
```bash
pkill -f "autoloader_main.py monitor"
```
**✅ Expected:** Process terminated

---

## 🧪 Testing

### 16. Run All Tests
```bash
uv run -s autoloader_main.py test --type all
```
**✅ Expected:**
- "🧪 Running Raw Pipeline Test... ✅ Raw data processing test passed"
- "🧪 Running Schematized Pipeline Test... ✅ Schema validation test passed"
- "🧪 Running Emergency Detection Test... ✅ Anomaly detection test passed"
- "🧪 Running S3 Access Validation Test... ✅ S3 bucket access test passed"
- "🧪 Running Data Partitioning Test... ✅ Date partitioning test passed"
- "✅ All tests completed successfully!"

### 17. Test Individual Components
```bash
uv run -s autoloader_main.py test --type s3-access
```
**✅ Expected:** "✅ s3-access test completed successfully!"

```bash
uv run -s autoloader_main.py test --type emergency
```
**✅ Expected:** "✅ emergency test completed successfully!"

---

## 🔄 Continuous Processing (Optional)

### 18. Test Continuous Mode (30 seconds)
```bash
timeout 30 uv run -s autoloader_main.py process --continuous --interval 10
```
**✅ Expected:**
- "🔄 Starting continuous processing (every 10s)"
- "📈 Processing batch at 2025-01-03..."
- Multiple processing cycles
- Terminated after 30 seconds

---

## ✅ Final Verification

### 19. Complete Status Check
```bash
uv run -s autoloader_main.py status
```
**✅ Expected:**
- All tables showing data
- All systems healthy
- No error messages

### 20. Verify All Components
```bash
# Check configuration files exist
ls -la unity_catalog_config.yaml s3-uploader-config.yaml

# Check main script is executable
uv run -s autoloader_main.py --help
```
**✅ Expected:**
- Configuration files exist
- Help message displays all available commands

---

## 🎯 Success Criteria

**All of the following should be true:**

- [ ] ✅ Environment variables are set correctly
- [ ] ✅ Infrastructure setup completed without errors
- [ ] ✅ System status shows all components healthy
- [ ] ✅ Test data was created and processed successfully
- [ ] ✅ All 4 Autoloader tables contain data
- [ ] ✅ Monitoring API responds correctly
- [ ] ✅ All tests pass
- [ ] ✅ Continuous processing works (if tested)

---

## 🚨 Troubleshooting

**If any step fails:**

1. **Environment Issues:** Verify all environment variables are set correctly
2. **Permission Issues:** Check Databricks token and AWS IAM role permissions
3. **Network Issues:** Verify connectivity to Databricks and AWS
4. **Port Issues:** Use different port for monitoring if 8000 is occupied

**Get help:**
```bash
uv run -s autoloader_main.py --help
uv run -s autoloader_main.py status
```

---

**🎉 SUCCESS: You now have a fully functional Autoloader-only sensor data pipeline!**

**Next:** Use the same commands in production with your production environment variables.
