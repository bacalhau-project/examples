#!/usr/bin/env bash

# Default values - override with environment variables
NUMBER_OF_JOBS=${NUMBER_OF_JOBS:-100}
TIME_BETWEEN_JOBS=${TIME_BETWEEN_JOBS:-30}
JOBS_PER_BATCH=${JOBS_PER_BATCH:-20}
JOB_SPEC=${JOB_SPEC:-job.yaml}
OUTPUT_FILE=${OUTPUT_FILE:-job_ids.txt}

# Create or truncate output file
> "$OUTPUT_FILE"

# Print job submission summary
echo "Submitting $NUMBER_OF_JOBS jobs to Bacalhau"
echo "  Batch size: $JOBS_PER_BATCH"
echo "  Time between batches: $TIME_BETWEEN_JOBS seconds"
echo "  Job spec: $JOB_SPEC"
echo "  Output file: $OUTPUT_FILE"
echo "------------------------"

# Show progress indicators
count=0
total=$NUMBER_OF_JOBS
start_time=$(date +%s)

# Submit jobs in batches
for ((i=1; i<=NUMBER_OF_JOBS; i++)); do
    # Submit job and capture ID
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    job_id=$(bacalhau job run --wait=false --id-only "$JOB_SPEC")
    
    # Show progress and save job ID
    echo "$timestamp - Job $i/$NUMBER_OF_JOBS - ID: $job_id"
    echo "$job_id" >> "$OUTPUT_FILE"
    count=$((count + 1))
    
    # Wait between batches
    if [ $((i % JOBS_PER_BATCH)) -eq 0 ] && [ $i -lt $NUMBER_OF_JOBS ]; then
        echo "Completed batch, waiting $TIME_BETWEEN_JOBS seconds..."
        sleep "$TIME_BETWEEN_JOBS"
    fi
done

# Display final summary
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "------------------------"
echo "All $count jobs submitted successfully in $duration seconds"
echo "Job IDs saved to $OUTPUT_FILE"

# Provide next steps
echo ""
echo "Next steps:"
echo "  - Check job status: python job_status_checker.py $OUTPUT_FILE"
echo "  - List all jobs by state: python list_all_jobs_by_state_and_node.py"