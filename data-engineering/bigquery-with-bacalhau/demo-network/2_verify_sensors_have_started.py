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
from datetime import datetime, timezone

def run_job_on_nodes(count=5):
    # Read and base64 encode the script
    with open('jobs/verify_sensors.py', 'rb') as f:
        script_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # Run the bacalhau job with the specified count and encoded script
    cmd = f"bacalhau job run jobs/run_python_script.yaml -V script_b64='{script_b64}' -V type=batch -V count={count} --id-only --wait"
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
            
            # Parse and format timestamp
            ts_value = latest["timestamp"]
            iso_timestamp = str(ts_value) # Default to string representation
            try:
                if isinstance(ts_value, (int, float)):
                    # Assume UTC if it's a number (Unix timestamp)
                    dt_object = datetime.fromtimestamp(ts_value, tz=timezone.utc)
                    iso_timestamp = dt_object.isoformat()
                elif isinstance(ts_value, str):
                    # Try parsing string, handling 'Z' for UTC
                    dt_object = datetime.fromisoformat(ts_value.replace('Z', '+00:00'))
                    # If it's naive after parsing, assume UTC
                    if dt_object.tzinfo is None:
                        dt_object = dt_object.replace(tzinfo=timezone.utc)
                    iso_timestamp = dt_object.isoformat()
                else:
                    # Handle unexpected type
                    print(f"Warning: Unexpected timestamp type '{type(ts_value)}'. Using original value.")
            except ValueError:
                 # Handle parsing errors
                 print(f"Warning: Could not parse timestamp '{ts_value}'. Using original value.")
            except Exception as e:
                print(f"Warning: Error processing timestamp '{ts_value}': {e}. Using original value.")

            table_data.append([
                result["node_id"][:12],  # Truncate node ID for better display
                result["row_count"],
                iso_timestamp, # Use formatted timestamp
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