import json
import os
import subprocess
import sys
from datetime import datetime
from io import StringIO

import pandas as pd


def run_command(command):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)

    # Find the position of the last closing bracket
    last_bracket_index = result.stdout.rfind("]")

    # Truncate the input to include only the JSON array
    truncated_input = result.stdout[: last_bracket_index + 1]
    return truncated_input.strip()


def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp) / 1e9).isoformat()


def main():
    orchestrator_node_raw = subprocess.run(
        "bacalhau config list --output json",
        shell=True,
        text=True,
        capture_output=True,
    )

    orchestrator_node_json = json.loads(orchestrator_node_raw.stdout)
    orchestrator_node_result = next(
        (
            entry["Value"]
            for entry in orchestrator_node_json
            if entry["Key"] == "node.clientapi.host"
        ),
        None,
    )

    if orchestrator_node_result:
        print(f"Getting all jobs from Orchestrator: {orchestrator_node_result}")
    else:
        print("Failed to get Orchestrator node details")
        sys.exit(1)

    commands = [
        "bacalhau job list --order-by created_at --order-reversed --limit 10000 --output json",
    ]

    results = {}
    for command in commands:
        results[command] = run_command(command)

    json_str = results[commands[0]]
    df = pd.read_json(StringIO(json_str))

    df["Name"] = df["Name"].apply(lambda x: "-".join(x.split("-")[:2]))
    df["CreateTime"] = pd.to_datetime(df["CreateTime"].apply(timestamp_to_iso))
    df["StateType"] = df["State"].apply(lambda x: x.get("StateType"))
    df = df.query("StateType != 'Failed'")

    state_order = ["Pending", "Queued", "Running", "Completed"]
    # Use .loc to avoid SettingWithCopyWarning
    df.loc[:, "StateType"] = pd.Categorical(
        df["StateType"], categories=state_order, ordered=True
    )

    # Ensure all states are represented in the summary table
    state_counts = df["StateType"].value_counts().reindex(state_order, fill_value=0)
    print("Summary Table of Each Unique State:")
    print(
        f"{'StateType':<15} {'Count':>10}"
    )  # Header with left-aligned StateType and right-aligned Count
    for state, count in state_counts.items():
        print(f"{state:<15} {count:>10}")

    print("\nList of 10 Most Recent Jobs for Each State:")
    grouped = df.groupby(
        "StateType", sort=False
    )  # Ensure the groupby respects the categorical order
    for state in state_order:
        group = grouped.get_group(state) if state in grouped.groups else pd.DataFrame()
        if group.empty:
            print(f"\nState: {state}")
            print(f"\nNo Jobs {state}")
        else:
            recent_jobs = group.nlargest(10, "CreateTime")
            print(f"\nState: {state}")
            print(
                recent_jobs[["Name", "Type", "StateType", "CreateTime"]].to_string(
                    index=False
                )
            )


if __name__ == "__main__":
    main()
