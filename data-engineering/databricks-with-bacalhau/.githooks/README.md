# Git Hooks

This directory contains git hooks to prevent common issues in Databricks notebooks.

## Setup

To enable these hooks in your local repository, run:

```bash
git config core.hooksPath .githooks
```

## Hooks Included

### pre-commit

Validates Databricks notebooks before commit to check for:

1. **Unsupported Triggers**: Prevents use of `processingTime` or `continuous` triggers which don't work on Databricks serverless compute
2. **Old Path Patterns**: Warns about nested directory structures when flat structure is preferred
3. **Missing Error Handling**: Warns about streaming queries without try/except blocks
4. **Hardcoded Values**: Warns about hardcoded S3 bucket names

## Manual Validation

You can manually run the validation script without committing:

```bash
uv run -s scripts/check-databricks-notebooks.py
```

## Bypassing Hooks (Emergency Only)

If you absolutely need to bypass the pre-commit hook (not recommended):

```bash
git commit --no-verify -m "your message"
```

## Troubleshooting

If the hooks aren't running:

1. Check that hooks path is configured:
   ```bash
   git config core.hooksPath
   ```
   Should output: `.githooks`

2. Ensure hooks are executable:
   ```bash
   chmod +x .githooks/pre-commit
   ```

3. Verify uv is installed for Python scripts:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```