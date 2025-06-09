# Bacalhau AWS Spot Cluster Setup Guide

## Commands

### Build/Run/Test
- `uv run -s util/get_available_regions.py [--show-all]` - Find regions with suitable spot instances
- `uv run -s util/get_ubuntu_amis.py` - Get Ubuntu AMIs for available regions
- `uv run -s util/update_config_with_regions.py` - Update config with available regions
- `uv run -s deploy_spot.py [create|list|destroy]` - Manage AWS spot instances

### Alternative (pip)
- `python util/get_available_regions.py`
- `python util/get_ubuntu_amis.py`
- `python util/update_config_with_regions.py`
- `python deploy_spot.py [create|list|destroy]`

## Code Style Guidelines
- Use f-strings for string formatting
- Use async/await for asynchronous operations
- Use rich library for terminal UI components
- Wrap AWS API calls with timeouts and error handling
- Use comprehensive logging with appropriate levels
- Follow PEP 8 naming conventions (snake_case for functions/variables)
- Error handling with try/except blocks and detailed error messages
- Organize code with proper separation of concerns
