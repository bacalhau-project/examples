# Bacalhau Job Queuing Example

A streamlined toolkit for submitting, tracking, and monitoring multiple jobs to a Bacalhau endpoint with controlled concurrency and elegant progress visualization.

## Prerequisites

- [Bacalhau CLI](https://docs.bacalhau.org/getting-started/installation) installed and configured
- Python 3.8+

## Setup

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

### 1. Submitting Jobs (Python UI)

Submit multiple jobs with rich terminal interface showing real-time progress:

```bash
python bacalhau_job_submitter.py --jobs 100 --batch-size 20 --interval 30 --job-spec job.yaml --output job_ids.json
```

Arguments:
- `--jobs`: Number of jobs to submit (default: 10)
- `--batch-size`: Jobs per batch (default: 20) 
- `--interval`: Seconds between batches (default: 30)
- `--job-spec`: Job specification file (default: job.yaml)
- `--output`: Output file for job IDs (JSON format)

### 2. Checking Job Status

Monitor the status of previously submitted jobs:

```bash
python job_status_checker.py job_ids.json --concurrency 10 --output status_results.json
```

Arguments:
- `job_ids_file`: JSON file containing job IDs from step 1
- `--concurrency`: Maximum parallel status checks (default: 10)
- `--summary`: Show only summary statistics
- `--output`: Save detailed results to JSON file

### 3. Listing Jobs by State

View all jobs grouped by their current state:

```bash
python list_all_jobs_by_state_and_node.py
```

### 4. Shell Script Alternative

For simple command-line job submission:

```bash
# Configure with environment variables (optional)
export NUMBER_OF_JOBS=50
export JOBS_PER_BATCH=10
export TIME_BETWEEN_JOBS=15

# Run the script
bash run_jobs.sh
```

Environment variables:
- `NUMBER_OF_JOBS`: Total jobs to submit (default: 100)
- `JOBS_PER_BATCH`: Jobs per batch (default: 20)
- `TIME_BETWEEN_JOBS`: Seconds between batches (default: 30)
- `JOB_SPEC`: Job specification file (default: job.yaml)
- `OUTPUT_FILE`: File for storing job IDs (default: job_ids.txt)

## Job Specifications

Two example job specs are provided:

1. **job.yaml** - Basic spec for single-job testing
2. **stress_job.yaml** - Higher job count (20) for stress testing

Both use the `stress-ng` container to generate controlled CPU load and include appropriate timeouts.

## Workflow Example

```bash
# 1. Submit 50 jobs in batches of 10
python bacalhau_job_submitter.py --jobs 50 --batch-size 10 --output my_jobs.json

# 2. Check job status with increased concurrency
python job_status_checker.py my_jobs.json --concurrency 20

# 3. View all jobs by state
python list_all_jobs_by_state_and_node.py
```