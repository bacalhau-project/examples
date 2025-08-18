# Development Rules and Best Practices

This document contains critical rules learned from development history to prevent recurring issues.

## 🚨 CRITICAL RULES - ALWAYS FOLLOW

### 1. Database Location
- **ALWAYS** use `sample-sensor/data/sensor_data.db` as the database location
- **NEVER** use `databricks-uploader/sensor_data.db`
- **NEVER** look at or reference `databricks-uploader/sensor_data.db`
- All scripts must mount from `sample-sensor/data/sensor_data.db`

### 2. Table and Schema Naming Convention
- **SQLite Table**: `sensor_readings` (NOT sensor_data)
- **Databricks Schema/Database**: `sensor_readings` (NOT sensor_data)
- **Databricks Tables**: Use `sensor_readings_` prefix:
  - `sensor_readings_ingestion`
  - `sensor_readings_validated`
  - `sensor_readings_enriched`
  - `sensor_readings_aggregated`
- **NEVER** use `sensor_data` as table name
- **NEVER** use `sensor_data_` prefix for tables
- **NEVER** use `sensor_data` as schema/database name
- All SQL queries must reference `sensor_readings`

### 3. Container Management
- **ALWAYS** use `--rm` flag with `docker run` for all containers
- **ALWAYS** stop containers with `docker stop` before removing
- **NEVER** leave test containers running after tests complete
- Use unique container names for parallel tests: `container-test-${TIMESTAMP}`

### 4. Metadata and Lineage
- **ALWAYS** attach job_id and node_id to every S3 upload
- **ALWAYS** create metadata.json alongside data.json uploads
- **ALWAYS** include S3 object tags for searchability
- **ALWAYS** track transformations through pipeline stages

## 📋 CONFIGURATION RULES

### 5. S3 Upload Paths
- Upload path must match pipeline type: `{pipeline_type}/{timestamp}/data.json`
- **NEVER** hardcode paths like `ingestion/` for all pipeline types
- Logging must accurately reflect actual upload location
- Each pipeline type maps to specific S3 bucket

### 6. Environment Variables
- **NEVER** use global settings in `~/.spot-deployer`
- **ALWAYS** use project-local configuration
- **ALWAYS** check for environment variable overrides
- Document all environment variables in `.env.example`

### 7. AWS Credentials
- **ALWAYS** disable AWS pager: `--no-paginate` or `AWS_PAGER=""`
- Support multiple credential sources (file, env, config)
- **NEVER** commit credentials to repository
- Use `/bacalhau_data/credentials/` for Docker mounts

## 🔧 CODE QUALITY RULES

### 8. Python Scripts
- **ALWAYS** use `uv run -s` instead of `python` for scripts
- Include metadata and dependencies at top of file:
  ```python
  #!/usr/bin/env uv run -s
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["boto3>=1.26.0", "pyyaml>=6.0"]
  # ///
  ```
- **ALWAYS** use `ruff` for Python linting
- Handle exceptions gracefully with meaningful error messages

### 9. Shell Scripts
- Line width limit: 80 characters (use `\` for continuation)
- **ALWAYS** use `set -euo pipefail` for error handling
- Add cleanup functions with `trap cleanup EXIT`
- Quote all variable expansions: `"$VAR"` not `$VAR`

### 10. Error Handling
- Check if files exist before operations
- Validate configuration before processing
- Log errors with context (timestamp, location, operation)
- Return meaningful exit codes

## 📊 DATA PROCESSING RULES

### 11. Schema Handling
- **NEVER** assume column names exist
- **ALWAYS** check schema dynamically before referencing columns
- Handle both old and new sensor data formats
- Use `coalesce()` for optional fields

### 12. JSON Format
- Uploader outputs flat JSON arrays: `[{...}, {...}]`
- **NEVER** wrap in objects: `{"records": [...]}`
- Databricks Auto Loader expects flat arrays
- Include timestamp in every record

### 13. State Management
- Persist state in `uploader-state/` directory
- Track last processed timestamp
- Record pipeline type changes
- Maintain upload history with job IDs

## 🐳 DOCKER RULES

### 14. Container Best Practices
- **ALWAYS** use specific image tags, not `latest` in production
- Mount configuration as read-only: `:ro`
- Use named volumes for persistent data
- Set resource limits for containers

### 15. Testing Containers
```bash
# Good - with cleanup
TEST_ID=$(date +%s)
CONTAINER="test-${TEST_ID}"
docker run --rm -d --name "$CONTAINER" image:tag
trap "docker stop $CONTAINER 2>/dev/null || true" EXIT

# Bad - no cleanup
docker run -d --name test-container image:tag
```

## 📝 DOCUMENTATION RULES

### 16. Code Comments
- **NO** comments unless explicitly requested
- Code should be self-documenting
- Use meaningful variable and function names
- Add docstrings for complex functions

### 17. Output Formatting
- Keep CLI output concise (< 4 lines unless requested)
- No unnecessary preambles or postambles
- Use bulk print for multiple lines, not repeated console.log
- Format timestamps consistently: ISO 8601

## 🔍 DEBUGGING RULES

### 18. Troubleshooting Order
1. Check container logs: `docker logs container-name`
2. Verify file paths and permissions
3. Check environment variables
4. Validate configuration files
5. Test with minimal reproducible example

### 19. Common Issues Checklist
- [ ] Database file exists at correct location?
- [ ] Table name is `sensor_readings`?
- [ ] Containers using `--rm` flag?
- [ ] S3 credentials configured?
- [ ] Pipeline type set correctly?
- [ ] State directory writable?

## 🚀 DEPLOYMENT RULES

### 20. Pre-deployment Checklist
- [ ] All tests passing
- [ ] No hardcoded credentials
- [ ] Metadata tracking enabled
- [ ] Container cleanup configured
- [ ] Documentation updated
- [ ] Error handling comprehensive

## 📊 MONITORING RULES

### 21. Operational Monitoring
- Track job IDs for all uploads
- Monitor pipeline type changes
- Log node IDs for distributed processing
- Record transformation lineage
- Alert on upload failures

## 🔄 PIPELINE RULES

### 22. Pipeline Types
- `raw` → `expanso-databricks-ingestion-us-west-2`
- `validated` → `expanso-databricks-validated-us-west-2`
- `enriched` → `expanso-databricks-enriched-us-west-2`
- `aggregated` → `expanso-databricks-aggregated-us-west-2`

### 23. Pipeline Transitions
- Record previous job_id when transitioning stages
- Maintain transformation history
- Update metadata at each stage
- Preserve original timestamps

## 🏗️ ARCHITECTURE & SEPARATION OF CONCERNS

### 24. Component Responsibilities

#### Sensor (sample-sensor/)
- **OWNS**: SQLite database with sensor readings
- **PROVIDES**: Read-only access to sensor_data.db
- **NEVER**: Modified by any other component
- **ISOLATION**: Complete - no other component writes to sensor

#### Databricks Uploader (databricks-uploader/)
- **OWNS**: Upload state management
- **READS**: Sensor database (read-only mount)
- **READS**: Pipeline configuration from pipeline-manager
- **WRITES**: Data to S3 buckets
- **NEVER**: Touches sensor database for writes
- **NEVER**: Creates Databricks tables or schemas
- **NEVER**: Manages bucket lifecycle

### 🚨 CRITICAL DATABASE ACCESS RULES

#### Databricks Uploader Database Access
**ABSOLUTELY CRITICAL - VIOLATION IS A PRODUCTION INCIDENT**:

1. **NEVER WRITE TO SENSOR DATABASE**
   - The uploader must ONLY open sensor_data.db in read-only mode
   - Use connection string: `file:{db_path}?mode=ro`
   - Set PRAGMA: `query_only=1` 
   - NEVER set journal modes or any write-affecting PRAGMAs
   - NEVER execute UPDATE, INSERT, DELETE, or CREATE statements
   - NEVER try to modify database settings (journal_mode, synchronous, etc.)

2. **READ-ONLY OPERATIONS ONLY**
   ```python
   # CORRECT - Read-only connection
   conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30.0)
   conn.execute("PRAGMA query_only=1;")
   # DO NOT ADD: conn.execute("PRAGMA journal_mode=WAL;")  # This is a WRITE operation!
   ```

3. **UPLOADER STATE MANAGEMENT**
   - Uploader maintains its OWN state in `/databricks-uploader/state/`
   - NEVER store uploader state in sensor database
   - Track upload progress in `upload_state.json`
   - Store pipeline config in separate `pipeline_config.db`

4. **ERROR MESSAGES TO WATCH FOR**
   - "attempt to write a readonly database" = CRITICAL BUG
   - "database is locked" = Normal, retry with backoff
   - "disk I/O error" = Check permissions, but NEVER try to fix by writing

5. **TESTING DATABASE ACCESS**
   ```bash
   # Test that uploader CANNOT write
   sqlite3 "file:sample-sensor/data/sensor_data.db?mode=ro" \
     "INSERT INTO sensor_readings VALUES(...);"
   # Should fail with: Error: attempt to write a readonly database
   ```

**WHY THIS MATTERS**: 
- The sensor owns its database completely
- Multiple writers = corruption
- Read-only access prevents ALL write-related bugs
- Production systems require strict separation of concerns

#### Pipeline Manager (pipeline-manager/)
- **OWNS**: Its own configuration database
- **WRITES**: Pipeline configuration atomically
- **PROVIDES**: Read-only configuration to uploader
- **MANAGES**: Pipeline type transitions
- **NEVER**: Directly uploads to S3
- **NEVER**: Touches sensor database

#### Databricks Notebooks (databricks-notebooks/)
- **OWNS**: All Databricks operations
- **MANAGES**: Delta table creation/cleanup
- **MANAGES**: Auto Loader setup
- **MANAGES**: Schema inference and evolution
- **MANAGES**: Bucket cleanup and initialization
- **CREATES**: Schema sample files after cleanup
- **NEVER**: Touches sensor database
- **NEVER**: Modifies uploader state

### 25. Data Flow Rules
1. **Sensor → Uploader**: Read-only mount of sensor_data.db
2. **Pipeline Manager → Uploader**: Read-only config mount
3. **Uploader → S3**: Write-only to buckets
4. **S3 → Databricks**: Read-only via Auto Loader
5. **No circular dependencies**: Each component has clear inputs/outputs

### 26. Configuration Mount Rules
- Pipeline Manager writes to `/config/pipeline-config.yaml`
- Uploader mounts as read-only: `/app/config/pipeline-config.yaml:ro`
- Configuration updates are atomic (write to temp, then rename)
- Uploader polls for config changes, never writes back

## 📊 DATABRICKS STREAMING RULES

### 27. Serverless Compute Triggers
**CRITICAL**: Databricks serverless compute does NOT support:
- `processingTime` trigger (e.g., `.trigger(processingTime="10 seconds")`)
- `continuous` trigger (e.g., `.trigger(continuous="1 second")`)

**ALWAYS USE** one of these supported triggers:
- `.trigger(availableNow=True)` - Process all available data then stop
- `.trigger(once=True)` - Process one micro-batch then stop
- No trigger specified - Uses default trigger (typically availableNow)

### 28. Auto Loader Best Practices
- Set `cloudFiles.useNotifications` to `false` unless SQS is configured
- Use `pathGlobFilter` to filter specific file patterns
- Set `recursiveFileLookup` to `false` for flat file structures
- Always specify `cloudFiles.schemaLocation` for schema inference
- Use `cloudFiles.allowOverwrites` to `true` for reprocessing

### 29. Streaming Query Checkpoint Requirements
**CRITICAL**: Databricks requires explicit checkpoint locations for ALL streaming queries:
- **ALWAYS** specify `.option("checkpointLocation", "path")` for writeStream
- This applies to ALL output formats: delta, console, memory, etc.
- Even test/debug queries need checkpoint locations
- Use unique paths for different queries to avoid conflicts
- Example: `.option("checkpointLocation", CHECKPOINT_BUCKET + "query_name/checkpoint")`

### 30. Table Management
- **ALWAYS** drop conflicting tables before creating new ones
- Check ALL schemas for conflicting table names
- Clean up checkpoints when changing data paths
- Use TRUNCATE TABLE for data cleanup, DROP TABLE for schema changes

### 31. File Structure
- Use flat file structures at bucket root when possible
- Format: `YYYYMMDD_HHMMSS_uniqueid.json`
- Avoid deeply nested directories requiring recursive lookups
- Use S3 object metadata/tags instead of separate metadata files

## 🐍 PYTHON SPECIFIC RULES

### 32. Method vs Property Access
- **ALWAYS** call methods with parentheses: `query.exception()` not `query.exception`
- Properties don't need parentheses: `query.isActive` (boolean property)
- Methods need parentheses: `query.exception()` (returns exception or None)
- Common Databricks streaming query patterns:
  - `query.isActive` - property (no parentheses)
  - `query.exception()` - method (needs parentheses)
  - `query.stop()` - method (needs parentheses)
  - `query.lastProgress` - property (no parentheses)

## 🔍 VALIDATION & LINTING

### 33. Pre-Upload Validation
**ALWAYS** validate notebooks before uploading to Databricks:
```bash
# Run comprehensive validation
uv run -s scripts/validate-all.py check

# Auto-fix issues where possible
uv run -s scripts/validate-all.py fix

# Format code
uv run -s scripts/validate-all.py format

# Run everything (fix, format, check)
uv run -s scripts/validate-all.py all
```

### 34. Validation Tools
- **validate-all.py**: Master validation script that runs all checks
- **validate-notebooks.py**: AST-based validation for method calls, streaming patterns
- **check-databricks-notebooks.py**: Pattern-based checks for triggers, paths
- **ruff**: Python linting with Databricks-specific configuration
- **NO MAKEFILES**: Use Python scripts with `uv run -s` instead

### 35. Common Validation Errors
1. **Method without parentheses**: `query.exception` → `query.exception()`
2. **Missing checkpoint**: Add `.option("checkpointLocation", "path")`
3. **Unsupported trigger**: Replace `processingTime` with `availableNow`
4. **Silent exceptions**: Replace `except: pass` with proper error handling

### 36. Git Pre-commit Hooks
Enable automatic validation before commits:
```bash
git config core.hooksPath .githooks
```
This runs validation automatically and prevents committing broken code.

### 37. Build Tools Philosophy
**NEVER USE MAKE** - Reasons:
- Make is a 1970s tool designed for C compilation
- Terrible error messages and debugging experience
- Tab vs space sensitivity causes hidden bugs
- Platform-specific behavior (GNU Make vs BSD Make)
- Poor support for modern Python workflows

**ALWAYS USE PYTHON SCRIPTS** with `uv run -s`:
- Clear, readable Python code
- Proper error handling and messages
- Cross-platform compatibility
- Native Python tooling integration
- Self-documenting with proper help text
- Type hints and modern Python features

## 📓 DATABRICKS NOTEBOOK RULES

### CRITICAL: Never Include These in Databricks Notebooks

1. **NEVER import PySpark** - It's pre-imported in Databricks
   - ❌ `from pyspark.sql.functions import *`
   - ❌ `from pyspark.sql.types import *`
   - ❌ `from pyspark.sql import SparkSession`
   - ✅ Just use the functions directly, they're already available

2. **NEVER use processingTime or continuous triggers** - Not supported in serverless
   - ❌ `.trigger(processingTime="10 seconds")`
   - ❌ `.trigger(continuous="1 second")`
   - ✅ `.trigger(availableNow=True)`
   - ✅ `.trigger(once=True)`

3. **ALWAYS validate notebooks before uploading**
   - Run the validator to catch these issues
   - Fix all errors and warnings
   - Test in Databricks after uploading

## 📁 FILE MANAGEMENT RULES

### 38. NEVER Create New Files Unless Explicitly Asked

**CRITICAL**: This is a common anti-pattern that must be avoided:

1. **ALWAYS edit existing files in place** - Use the Edit tool to modify existing files
2. **Do NOT create copies or backups** unless explicitly requested by the user
3. **Do NOT create temporary files** in /tmp or elsewhere unless absolutely necessary
4. **Do NOT use `cp` to create new versions** - edit the original file directly
5. **Do NOT create documentation files** (README.md, GUIDE.md, etc.) unless explicitly requested
6. **Do NOT create "improved" or "better" versions** of existing files
7. **Do NOT create "simplified" or "clean" versions** - EDIT THE EXISTING FILE INSTEAD
8. **When asked to clean up or simplify** - ALWAYS edit the existing file, NEVER create a new one

### 39. When Editing Files

1. **Use direct file editing** - Use the Edit tool to modify files in place
2. **Make changes directly to the target file** - Don't create intermediate files
3. **Transform content in memory** - If you need to process content, do it in memory
4. **Preserve file structure** - Don't reorganize or restructure unless asked

### 40. File Operation Examples

#### ❌ BAD - Creates unnecessary files:
```bash
# Don't do this - creates unnecessary copies
cp original.py backup.py
cp flexible-autoloader.py setup-and-run-autoloader.py  # NO!
cat > /tmp/header.txt << EOF
# Header content
EOF
cat /tmp/header.txt original.py > new.py
mv new.py original.py

# NEVER do this when asked to simplify/clean up:
write simplified-notebook.py  # NO! Edit the existing notebook instead
write clean-version.py  # NO! Clean the existing file
write better-implementation.py  # NO! Improve the existing file
```

#### ✅ GOOD - Edits in place:
```python
# Do this - edit file directly using the Edit tool
# Read the existing file
content = read_file('original.py')
# Modify in memory
new_content = add_header(content)
# Write back to the SAME file
edit_file('original.py', old_content, new_content)
```

### 41. Exception Cases for Creating Files

Only create new files when:
1. User explicitly says "create a new file" or "create a new script"
2. User explicitly says "make a copy" or "backup"
3. Creating a genuinely new script/document that doesn't exist yet
4. Creating required config files that don't exist (.env, config.yaml, etc.)
5. User asks for a new feature that requires a new file

## 🚨 CRITICAL FILE HANDLING RULES

### STOP CREATING MULTIPLE FILES

**ABSOLUTELY NEVER DO THIS:**
1. When asked to "clean up" a file - EDIT THE EXISTING FILE
2. When asked to "simplify" a file - EDIT THE EXISTING FILE  
3. When asked to "improve" a file - EDIT THE EXISTING FILE
4. When asked to "fix" a file - EDIT THE EXISTING FILE
5. NEVER create "v2", "clean", "simple", "better" versions
6. NEVER create temporary versions then rename them
7. ALWAYS work with the file that exists

**ONE FILE, ONE PURPOSE** - If a file exists for a purpose, that's THE file. Edit it in place.

## ⚠️ NEVER DO THIS

1. **NEVER** reference `databricks-uploader/sensor_data.db`
2. **NEVER** use `sensor_data` as table, schema, or database name
3. **NEVER** use `sensor_data_` prefix for Databricks tables
4. **NEVER** hardcode S3 paths
5. **NEVER** skip the `--rm` flag on containers
6. **NEVER** commit credentials
7. **NEVER** assume column names exist
8. **NEVER** use global configuration
9. **NEVER** skip error handling
10. **NEVER** leave containers running after tests
11. **NEVER** upload without metadata
12. **NEVER** use `processingTime` trigger in Databricks serverless
13. **NEVER** use `continuous` trigger in Databricks serverless
14. **NEVER** omit checkpoint location in streaming queries (even for console/test)
15. **NEVER** let uploader write to sensor database
16. **NEVER** let uploader execute PRAGMA journal_mode on sensor database (it's a WRITE operation!)
17. **NEVER** let uploader create Databricks tables
18. **NEVER** let pipeline manager directly upload to S3
19. **NEVER** create schema samples outside of Databricks notebooks
20. **NEVER** use Make or Makefiles - use Python scripts with uv run instead

## ✅ ALWAYS DO THIS

1. **ALWAYS** use `sample-sensor/data/sensor_data.db`
2. **ALWAYS** use `sensor_readings` table
3. **ALWAYS** attach job_id and node_id to uploads
4. **ALWAYS** use `--rm` with docker run
5. **ALWAYS** clean up test resources
6. **ALWAYS** check schema dynamically
7. **ALWAYS** use project-local config
8. **ALWAYS** handle errors gracefully
9. **ALWAYS** track lineage metadata
10. **ALWAYS** validate before processing
11. **ALWAYS** maintain separation of concerns between components
12. **ALWAYS** mount sensor database as read-only in uploader
13. **ALWAYS** let Databricks notebooks manage all Databricks operations
14. **ALWAYS** create schema samples in notebooks after cleanup

---

Last Updated: 2025-08-08
Version: 1.0.0