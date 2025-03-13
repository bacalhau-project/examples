# Bacalhau AWS Spot Cluster Setup Guide

## Commands

### Build/Run/Test
- `uv run -s util/get_available_regions.py [--show-all]` - Find regions with suitable spot instances
- `uv run -s util/get_ubuntu_amis.py` - Get Ubuntu AMIs for available regions
- `uv run -s util/update_config_with_regions.py` - Update config with available regions
- `uv run -s deploy_spot_v2.py [create|list|destroy|nuke]` - Manage AWS spot instances (latest version)
- `uv run -s deploy_spot_v2.py --dry-run [command]` - Test operations without making changes
- `uv run -s deploy_spot_v2.py --debug` - Run with verbose debugging output

### Alternative (pip)
- `python util/get_available_regions.py`
- `python util/get_ubuntu_amis.py`
- `python util/update_config_with_regions.py`
- `python deploy_spot_v2.py [create|list|destroy|nuke]`

## Code Style Guidelines
- Use f-strings for string formatting
- Use async/await for concurrency with proper task handling
- Use rich library for terminal UI (progress bars, tables, live displays)
- Wrap AWS API calls with timeouts, retries, and comprehensive error handling
- Use hierarchical logging with different levels (DEBUG, INFO, ERROR)
- Follow PEP 8 naming conventions (snake_case for functions/variables)
- Use type annotations for function parameters and return values
- Implement idempotent operations and proper resource cleanup for AWS resources
- Organize code with modular architecture (aws/, config/, spot/, ui/ packages)
- Use proper signal handling for clean shutdowns
- Implement state management for tracking operation progress