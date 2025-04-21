#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "tabulate",
# ]
# ///

import subprocess
import json
import base64
from tabulate import tabulate

def run_job_on_nodes(count=5):
    # Read and base64 encode the script
    with open('jobs/verify_location.py', 'rb') as f:
        script_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # Run the bacalhau job with the specified count and encoded script
    cmd = f"bacalhau job run jobs/run_python_script.yaml -V script_b64='{script_b64}' -V count={count} --id-only --wait"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running job:", result.stderr)
        return None
    
    # Extract job ID from the output
    job_id = result.stdout.strip()
    return job_id

def get_job_results(job_id):
    # Get job results in JSON format
    cmd = f"bacalhau job describe {job_id} --output json"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error getting job results:", result.stderr)
        return []
    
    try:
        job_data = json.loads(result.stdout)
        executions = job_data.get("Executions", {}).get("Items", [])
        
        # Extract the relevant data from each execution
        parsed_executions = []
        for exec in executions:
            if exec.get("RunOutput", {}).get("Stdout"):
                try:
                    output = json.loads(exec["RunOutput"]["Stdout"].strip())
                    parsed_executions.append({
                        "id": exec["ID"],
                        "node_id": exec["NodeID"],
                        "config_file": output["config_file"],
                        "identity_file": output["identity_file"],
                        "location": output["location"],
                        "latitude": output["latitude"],
                        "longitude": output["longitude"]
                    })
                except json.JSONDecodeError:
                    continue
        
        return parsed_executions
    except json.JSONDecodeError:
        print("Error parsing job results JSON")
        return []

def main():
    # Run the job on 5 nodes
    job_id = run_job_on_nodes(5)
    if not job_id:
        return
    
    # Get and parse results
    results = get_job_results(job_id)
    
    # Prepare table data
    table_data = []
    for exec in results:
        table_data.append([
            exec["id"],
            exec["node_id"],
            exec["config_file"],
            exec["identity_file"],
            exec["location"],
            f"{exec['latitude']:.4f}, {exec['longitude']:.4f}"
        ])
    
    # Print table
    headers = ['Execution ID', 'Node ID', 'Config File', 'Identity File', 'Location', 'Coordinates']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))

if __name__ == "__main__":
    main() 