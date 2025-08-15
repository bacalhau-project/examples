# Databricks Notebook Validation System

This project includes a comprehensive validation system to catch syntax errors and issues in Databricks notebooks before they're uploaded to your workspace.

## Components

### 1. Standalone Validator Script
**Location:** `scripts/validate-databricks-notebook.py`

Validates Databricks notebook syntax and checks for common issues:
- Python syntax errors
- Unclosed parentheses, brackets, etc.
- Unnecessary imports (PySpark is pre-imported in Databricks)
- Environment variable usage warnings
- Local file path warnings

**Usage:**
```bash
# Basic validation
uv run -s scripts/validate-databricks-notebook.py databricks-notebooks/my-notebook.py

# Show code context for errors
uv run -s scripts/validate-databricks-notebook.py databricks-notebooks/my-notebook.py \
  --show-context

# Strict mode (treat warnings as errors)
uv run -s scripts/validate-databricks-notebook.py databricks-notebooks/my-notebook.py \
  --strict

# JSON output for CI/CD integration
uv run -s scripts/validate-databricks-notebook.py databricks-notebooks/my-notebook.py \
  --json
```

### 2. Pre-Upload Validation
**Location:** Built into `scripts/upload-and-run-notebook.py`

The upload script now automatically validates notebooks before uploading:
```bash
# Validates automatically before upload
uv run -s scripts/upload-and-run-notebook.py \
  --notebook databricks-notebooks/my-notebook.py

# Skip validation if needed
uv run -s scripts/upload-and-run-notebook.py \
  --notebook databricks-notebooks/my-notebook.py \
  --skip-validation
```

### 3. Git Pre-Commit Hook
**Location:** `.githooks/pre-commit-databricks`

Automatically validates all Databricks notebooks before committing.

**Installation:**
```bash
# Install the pre-commit hook
ln -sf ../../.githooks/pre-commit-databricks .git/hooks/pre-commit

# Make it executable
chmod +x .githooks/pre-commit-databricks
```

**Usage:**
The hook runs automatically on `git commit`. To skip validation:
```bash
git commit --no-verify
```

### 4. GitHub Actions CI
**Location:** `.github/workflows/validate-notebooks.yml`

Validates notebooks on:
- Push to main/master
- Pull requests
- Changes to notebooks or validator script

The CI runs both normal and strict validation for pull requests.

## Common Issues Detected

### Syntax Errors
- Unclosed parentheses, brackets, braces
- Invalid Python syntax
- Indentation errors

### Databricks-Specific Issues
- Unnecessary PySpark imports (already available in Databricks)
- Use of `os.environ` (should use cluster config)
- Local file paths that won't work in Databricks
- dbutils import (pre-imported)

### Warnings vs Errors
- **Errors:** Block upload/commit by default
- **Warnings:** Informational, can be promoted to errors with `--strict`

## Validation Flow

```
1. Developer writes/modifies notebook
   ↓
2. Pre-commit hook validates (optional)
   ↓
3. Upload script validates before upload
   ↓
4. GitHub Actions validates on push/PR
   ↓
5. Notebook uploaded to Databricks
```

## Troubleshooting

### "SyntaxError: '(' was never closed"
This usually means:
1. Missing closing parenthesis, bracket, or brace
2. Multi-line statement not properly continued
3. String literal not properly closed

Run the validator with `--show-context` to see the exact location:
```bash
uv run -s scripts/validate-databricks-notebook.py notebook.py --show-context
```

### False Positives
If the validator reports false positives:
1. Check if the notebook uses Databricks-specific magic commands correctly
2. Ensure `# COMMAND ----------` separators are properly formatted
3. Use `--skip-validation` as a temporary workaround

### Performance
For large notebooks, validation typically takes < 1 second.

## Best Practices

1. **Always validate before uploading** - The upload script does this automatically
2. **Install the pre-commit hook** - Catch issues before they reach the repository
3. **Fix warnings** - They often indicate code that won't work optimally in Databricks
4. **Use strict mode in CI** - Ensure high code quality in pull requests
5. **Keep validator updated** - Add new checks as you discover common issues

## Extending the Validator

To add custom validation rules, edit `scripts/validate-databricks-notebook.py`:

```python
def validate_custom_rules(self, code: str, line_offset: int = 0):
    """Add your custom validation logic here."""
    warnings = []
    # Your validation logic
    return warnings
```

Then call it in the `validate_cell` method.