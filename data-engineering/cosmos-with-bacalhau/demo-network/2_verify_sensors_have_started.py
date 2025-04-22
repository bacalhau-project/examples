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
import time
from tabulate import tabulate
from datetime import datetime

def run_job_on_nodes(count=5):
    # Read and base64 encode the script
    with open('jobs/verify_sensors.py', 'rb') as f:
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
                    if output.get("status") == "success":
                        parsed_executions.append({
                            "node_id": exec["NodeID"],
                            "row_count": output.get("row_count", 0),
                            "latest_entry": output.get("latest_entry", {})
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
    
    print(f"\nJob ID: {job_id}")
    print("\nQuerying results...")
    
    # Get and parse results
    results = get_job_results(job_id)
    
    if not results:
        print("\nNo sensor data found.")
        return
    
    # Sort results by node_id
    results.sort(key=lambda x: x["node_id"])
    
    # Prepare table data
    table_data = []
    for result in results:
        latest = result["latest_entry"]
        if latest:
            readings = latest["readings"]
            table_data.append([
                result["node_id"][:12],  # Truncate node ID for better display
                result["row_count"],
                latest["timestamp"],
                latest["sensor_id"],
                readings["temperature"],
                readings["humidity"],
                readings["pressure"],
                readings["vibration"],
                readings["voltage"],
                latest["status"],
                latest["location"],
                latest["coordinates"]
            ])
    
    # Print table with all readings
    headers = [
        'Node ID', 'Row Count', 'Timestamp', 'Sensor ID', 
        'Temp', 'Humidity', 'Pressure', 'Vibration', 'Voltage',
        'Status', 'Location', 'Coordinates'
    ]
    print("\nSensor Data from Nodes:")
    print(tabulate(table_data, headers=headers, tablefmt='grid'))

if __name__ == "__main__":
    main() 