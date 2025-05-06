#!/usr/bin/env python3

import json
import sys
import subprocess
import asyncio
import logging
from datetime import datetime
from io import StringIO
import pandas as pd
from rich.console import Console
from rich.table import Table

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

console = Console()

def timestamp_to_iso(timestamp):
    """Convert nanosecond timestamp to ISO format."""
    return datetime.fromtimestamp(int(timestamp) / 1e9).isoformat()

async def get_jobs():
    """Get list of jobs from Bacalhau."""
    try:
        cmd = ["bacalhau", "job", "list", "--order-by", "created_at", 
               "--order-reversed", "--limit", "10000", "--output", "json"]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Error getting job list: {stderr.decode()}")
            sys.exit(1)
        
        return json.loads(stdout.decode())
    
    except Exception as e:
        logger.error(f"Exception when getting job list: {str(e)}")
        sys.exit(1)

def main():
    # Get job list
    jobs = asyncio.run(get_jobs())
    
    # Convert to dataframe
    df = pd.DataFrame(jobs)
    
    # Process job data
    df["Name"] = df["Name"].apply(lambda x: "-".join(x.split("-")[:2]))
    df["CreateTime"] = pd.to_datetime(df["CreateTime"].apply(timestamp_to_iso))
    df["StateType"] = df["State"].apply(lambda x: x.get("StateType"))
    df = df.query("StateType != 'Failed'")
    
    # Define state order
    state_order = ["Pending", "Queued", "Running", "Completed"]
    df.loc[:, "StateType"] = pd.Categorical(
        df["StateType"], categories=state_order, ordered=True
    )
    
    # Count jobs by state
    state_counts = df["StateType"].value_counts().reindex(state_order, fill_value=0)
    
    # Display summary table
    summary_table = Table(title="Summary of Jobs by State", show_header=True, header_style="bold magenta")
    summary_table.add_column("State", style="cyan")
    summary_table.add_column("Count", style="green", justify="right")
    summary_table.add_column("Percentage", style="yellow", justify="right")
    
    total = len(df)
    for state, count in state_counts.items():
        percentage = (count / total) * 100 if total > 0 else 0
        summary_table.add_row(
            state,
            str(count),
            f"{percentage:.1f}%"
        )
    
    console.print(summary_table)
    
    # Display recent jobs for each state
    console.print("\n[bold]Recent Jobs by State:[/bold]")
    
    grouped = df.groupby("StateType", sort=False)
    for state in state_order:
        if state not in grouped.groups:
            console.print(f"\n[bold cyan]State: {state}[/bold cyan]")
            console.print("No jobs in this state")
            continue
            
        group = grouped.get_group(state)
        recent_jobs = group.nlargest(10, "CreateTime")
        
        jobs_table = Table(show_header=True, header_style="bold")
        jobs_table.add_column("Name", style="green")
        jobs_table.add_column("Type", style="cyan")
        jobs_table.add_column("Create Time", style="magenta")
        
        for _, job in recent_jobs.iterrows():
            jobs_table.add_row(
                job["Name"],
                job["Type"],
                job["CreateTime"].strftime("%Y-%m-%d %H:%M:%S")
            )
        
        console.print(f"\n[bold cyan]State: {state}[/bold cyan]")
        console.print(jobs_table)

if __name__ == "__main__":
    main()