# Databricks Serverless Compute Fixes

## Issue Fixed
Databricks Auto Loader pipelines were failing with ProcessingTime trigger errors because serverless compute doesn't support continuous or processingTime triggers.

## Changes Made

### 1. Fixed Streaming Triggers
Replaced all `processingTime` triggers with `availableNow=True` in:
- `databricks-notebooks/flexible-autoloader.py`
- `databricks-notebooks/setup-and-run-autoloader.py`
- `databricks-notebooks/debug-autoloader.py`

**Before:**
```python
.trigger(processingTime="10 seconds")
```

**After:**
```python
.trigger(availableNow=True)
```

### 2. Added Development Rules
Updated `DEVELOPMENT_RULES.md` with Databricks-specific guidelines:
- Section 24: Serverless Compute Triggers
- Section 25: Auto Loader Best Practices
- Section 26: Table Management
- Section 27: File Structure

### 3. Created Validation Script
Added `scripts/check-databricks-notebooks.py` to detect:
- Unsupported triggers (processingTime, continuous)
- Old nested path patterns
- Missing error handling
- Hardcoded S3 bucket names

### 4. Set Up Git Pre-commit Hook
Created `.githooks/pre-commit` to automatically validate notebooks before commit.

To enable:
```bash
git config core.hooksPath .githooks
```

### 5. Added Ruff Configuration
Enhanced `databricks-notebooks/.ruff.toml` for Python linting with Databricks-specific ignores.

## How to Use

### Running the Notebook
The fixed `flexible-autoloader.py` notebook will now:
1. Clean up conflicting tables on startup
2. Use `availableNow` triggers that work with serverless compute
3. Process flat JSON files from bucket root
4. Handle schema evolution properly

### Validating Changes
Before committing any Databricks notebook changes:
```bash
# Manual validation
uv run -s scripts/check-databricks-notebooks.py

# Automatic validation (if hooks configured)
git commit -m "your message"
```

### Supported Triggers
On Databricks serverless compute, use only:
- `.trigger(availableNow=True)` - Process all available data then stop
- `.trigger(once=True)` - Process one micro-batch then stop
- No trigger - Uses default (typically availableNow)

## Prevention Measures

1. **Pre-commit Hook**: Automatically checks for unsupported triggers
2. **Validation Script**: Can be run manually or in CI/CD
3. **Development Rules**: Documents best practices
4. **Ruff Configuration**: Catches Python issues

## Testing
After these fixes, the pipelines should:
- Start without ProcessingTime errors
- Process files from S3 successfully
- Handle the flat file structure (YYYYMMDD_HHMMSS_uniqueid.json)
- Work with Databricks serverless compute

## Next Steps
1. Upload the fixed notebook to Databricks
2. Run the cleanup section to drop conflicting tables
3. Start the pipelines - they'll use availableNow triggers
4. Monitor for successful data ingestion