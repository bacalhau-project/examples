# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands
- Build C# application: `cd cosmos-uploader && ./build.sh [--tag VERSION] [--no-tag]` 
- Run cosmos query: `./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml [options]`
- Run sensor manager: `./sensor-manager.sh [command] [options]`
  - Commands: start, stop, reset, clean, build, logs, query, diagnostics, monitor, cleanup
- Run benchmarks: `python3 benchmark_cosmos.py --config [config_path] --output [output_dir]`

## Code Style Guidelines
- Python: Use type annotations, follow PEP 8, handle exceptions with specific error types
- C#: Use nullable reference types, follow Microsoft naming conventions (.NET 8.0)
- Shell scripts: Use `set -e` at script start, implement error handling with proper exit codes
- Keep line lengths below 100 characters where possible
- Use descriptive variable names in camelCase (C#) or snake_case (Python)
- Document public APIs and functions with meaningful comments
- Validate input data before processing
- Proper error handling with try/catch blocks and logging
- Structure imports: standard library first, then third-party, then local
- Use dependency injection for services in C# code
- Configure applications via YAML files or environment variables