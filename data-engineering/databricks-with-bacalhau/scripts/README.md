# Infrastructure Setup Scripts

Scripts for setting up AWS S3 infrastructure and Databricks integration for the data pipeline.

All scripts should be run from the main `databricks-with-bacalhau` directory.

## 🚀 Quick Start

```bash
# 1. Complete infrastructure setup
uv run -s setup.py all

# 2. Verify everything is working
uv run -s setup.py verify

# 3. Test Databricks S3 access
uv run -s setup.py test-s3
```

## 🛠️ Main Command: `setup.py`

The central script for infrastructure setup and verification:

```bash
# Show all commands
uv run -s setup.py --help

# Available commands:
uv run -s setup.py all         # Complete infrastructure setup
uv run -s setup.py verify      # Verify infrastructure is working
uv run -s setup.py test-s3     # Test Databricks S3 read/write/delete
uv run -s setup.py buckets     # Check S3 bucket status
uv run -s setup.py databricks  # Test Databricks CLI configuration
uv run -s setup.py help        # Show command help
```

## 🔧 Individual Scripts

All scripts are self-contained with dependencies declared in the script header:

### Databricks Scripts
- `databricks-setup-and-test.py` - Setup and test Databricks S3 access
- `run-databricks-notebook.py` - Run any notebook file on Databricks
- `run-databricks-sql.py` - Run SQL files on Databricks

### Setup & Verification Scripts
- `query-s3-buckets.py` - Query and display S3 bucket contents
- `test-s3-uploader-west.py` - Test S3 configuration
- `test-databricks-s3-access.py` - Comprehensive S3 access test

### Infrastructure Scripts
- `create-s3-buckets.sh` - Create S3 buckets in us-west-2
- `update-iam-role-policy-west.sh` - Update IAM role for S3 access
- `check-s3-buckets-west.sh` - Check if S3 buckets exist

## 📝 Examples

### Run a Databricks notebook
```bash
# Run a Python notebook
uv run -s run-databricks-notebook.py ../databricks-notebooks/test-s3-access.py

# Run a SQL file as notebook
uv run -s run-databricks-sql.py ../sql/create-tables.sql

# Or use the pipeline command
uv run -s pipeline.py notebook ../databricks-notebooks/test-s3-access.py
```

### Test Databricks S3 access
```bash
# Quick test (read/write only)
uv run -s test-databricks-s3-access.py --quick

# Comprehensive test (all operations)
uv run -s test-databricks-s3-access.py
```

### Query S3 buckets
```bash
# Check bucket contents
uv run -s query-s3-buckets.py
```

## 🛠️ No Installation Required!

All scripts use `uv run -s` which:
- Automatically installs dependencies in an isolated environment
- Requires no virtual environment setup
- Ensures consistent dependency versions
- Runs immediately without setup

Just clone the repo and run any script with `uv run -s`!