# AGENTS.md - Coding Guidelines for Databricks with Bacalhau

## Build/Lint/Test Commands
```bash
# Lint with ruff (required before commits)
ruff check . && ruff format .

# Run all tests
python -m pytest databricks-uploader/

# Run single test
uv run -s databricks-uploader/test_pipeline_upload_cycle.py
```

## Code Style Guidelines
- **Python**: Use `uv run -s` for all scripts with inline dependencies at top
- **Imports**: Standard library → Third-party → Local (alphabetical within groups)
- **Formatting**: 80 char lines, use `\` for continuation, ruff for auto-format
- **Types**: Use type hints for function signatures and complex data structures
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Error Handling**: Explicit try/except with specific exceptions, log errors
- **AWS CLI**: Always use `--no-pager` flag to prevent interactive prompts
- **Paths**: Use absolute paths for file operations, Path objects preferred
- **Testing**: Mock external services (Databricks, S3), use pytest fixtures
- **Config**: YAML files with environment variable overrides, hot-reload support