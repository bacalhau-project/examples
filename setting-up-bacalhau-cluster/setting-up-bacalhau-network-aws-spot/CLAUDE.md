# Bacalhau AWS Spot Cluster Setup Guide

## Commands

### Build/Run/Test
- `uv run -s util/get_available_regions.py [--show-all]` - Find regions with suitable spot instances
- `uv run -s util/get_ubuntu_amis.py` - Get Ubuntu AMIs for available regions
- `uv run -s util/update_config_with_regions.py` - Update config with available regions
- `uv run -s deploy_spot.py [create|list|destroy|nuke]` - Manage AWS spot instances
- `uv run -s deploy_spot.py --dry-run [command]` - Test operations without making changes
- `uv run -s deploy_spot.py --debug` - Run with verbose debugging output
- `uv run -s delete_vpcs.py` - Clean up VPCs created by the deployment script

### Linting
- `ruff check .` - Run linter on all Python files
- `ruff format .` - Auto-format Python code to match style guidelines

### Alternative (pip)
- `python -m util.get_available_regions [--show-all]`
- `python -m util.get_ubuntu_amis`
- `python -m util.update_config_with_regions`
- `python deploy_spot.py [create|list|destroy|nuke]`

## Code Style Guidelines
- Use f-strings for string formatting
- Use async/await for proper concurrency with task handling and error propagation
- Leverage rich library for terminal UI (progress bars, tables, live displays)
- Implement comprehensive error handling with timeouts and retries for AWS API calls
- Structure logging with levels (DEBUG, INFO, WARNING, ERROR) and consistent formatting
- Follow PEP 8 naming conventions (snake_case for variables/functions, UPPER_CASE for constants)
- Include type annotations for all function parameters and return values
- Design idempotent operations with proper resource cleanup for AWS resources
- Organize code into logical modules (aws/, config/, spot/, ui/ packages)
- Implement proper signal handling and state management for tracking operation progress