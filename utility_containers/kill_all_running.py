#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
# ]
# ///

import json
import subprocess


def run_bacalhau_command(command):
    """Run a bacalhau command and return the output."""
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(result.stderr)
        return None
    return result.stdout


def list_jobs():
    """List all jobs and return the JSON output."""
    command = "bacalhau job list --output json --limit 1000"
    output = run_bacalhau_command(command)
    if output:
        return json.loads(output)
    return []


def stop_job(job_id):
    """Stop a job by its ID."""
    command = f"bacalhau job stop {job_id}"
    output = run_bacalhau_command(command)
    if output:
        print(f"Stopped job {job_id}")
    else:
        print(f"Failed to stop job {job_id}")


def main():
    jobs = list_jobs()
    if not jobs:
        print("No jobs found or failed to list jobs.")
        return

    for job in jobs:
        if job.get("State", {}).get("StateType") == "Running":
            job_id = job.get("ID")
            if job_id:
                print(f"Stopping job {job_id}...")
                stop_job(job_id)
            else:
                print("Job ID not found for a running job.")
        else:
            print(f"Job {job.get('ID')} is not running.")


if __name__ == "__main__":
    main()
