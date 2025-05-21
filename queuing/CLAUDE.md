# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run job submitter with UI
python bacalhau_job_submitter.py --jobs [NUM] --batch-size [SIZE] --interval [SECS] --job-spec job.yaml --output job_ids.json

# Check job status 
python job_status_checker.py job_ids.json --concurrency [NUM] --output status_results.json

# List jobs by state
python list_all_jobs_by_state_and_node.py

# Simple CLI job submission
bash run_jobs.sh
```

## Code Style Guidelines

- **Imports**: Standard library first, then third-party, alphabetized within groups
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Formatting**: 4-space indentation, ~88 character line limit
- **Error Handling**: Use try/except with specific error types and logging
- **Documentation**: Use docstrings for functions and inline comments for complex logic
- **Logging**: Use the logging module with consistent format `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Async**: Use asyncio for concurrent operations
- **UI Components**: Use rich library for terminal UI (tables, progress bars, etc.)
- **Job Management**: Process jobs in batches with configurable concurrency limits
- **Data Processing**: Use pandas for data manipulation when appropriate