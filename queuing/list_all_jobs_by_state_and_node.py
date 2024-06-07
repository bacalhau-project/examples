import pandas as pd
from datetime import datetime
import json
from io import StringIO
import subprocess

def run_command(command):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    return result.stdout.strip()

def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp) / 1e9).isoformat()

def main():
    commands = [
        "BACALHAU_NODE_CLIENTAPI_HOST=52.176.177.175 && bacalhau job list --order-by created_at --order-reversed --limit 10000 --output json",
    ]
    
    results = {}
    for command in commands:
        results[command] = run_command(command)
    
    json_str = results[commands[0]]
    df = pd.read_json(StringIO(json_str))
    
    df['Name'] = df['Name'].apply(lambda x: '-'.join(x.split('-')[:2]))
    df['CreateTime'] = pd.to_datetime(df['CreateTime'].apply(timestamp_to_iso))
    df['StateType'] = df['State'].apply(lambda x: x.get('StateType'))
    df = df.query("StateType != 'Failed'")

    state_order = ['Pending', 'Running', 'Completed']
    # Use .loc to avoid SettingWithCopyWarning
    df.loc[:, 'StateType'] = pd.Categorical(df['StateType'], categories=state_order, ordered=True)

    # Ensure all states are represented in the summary table
    state_counts = df['StateType'].value_counts().reindex(state_order, fill_value=0)
    print("Summary Table of Each Unique State:")
    print(f"{'StateType':<15} {'Count':>10}")  # Header with left-aligned StateType and right-aligned Count
    for state, count in state_counts.items():
        print(f"{state:<15} {count:>10}")

    print("\nList of 10 Most Recent Jobs for Each State:")
    grouped = df.groupby('StateType', sort=False)  # Ensure the groupby respects the categorical order
    for state in state_order:
        group = grouped.get_group(state) if state in grouped.groups else pd.DataFrame()
        if group.empty:
            print(f"\nState: {state}")
            print(f"\nNo Jobs {state}")
        else:
            recent_jobs = group.nlargest(10, 'CreateTime')
            print(f"\nState: {state}")
            print(recent_jobs[['Name', 'Type', 'StateType', 'CreateTime']].to_string(index=False))
if __name__ == "__main__":
    main()

