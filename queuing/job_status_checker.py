#!/usr/bin/env python3

import asyncio
import argparse
import json
import logging
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

console = Console()

async def get_job_status(job_id):
    """Get the status of a single job."""
    try:
        cmd = ["bacalhau", "job", "status", job_id, "--json"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Error getting status for job {job_id}: {stderr.decode()}")
            return {"job_id": job_id, "status": "ERROR", "error": stderr.decode()}
        
        status_json = json.loads(stdout.decode())
        return {"job_id": job_id, "status": status_json}
    
    except Exception as e:
        logger.error(f"Exception when checking job {job_id}: {str(e)}")
        return {"job_id": job_id, "status": "ERROR", "error": str(e)}

async def check_job_statuses(job_ids, concurrency=10):
    """Check the status of multiple jobs with concurrency limit."""
    results = []
    
    with Progress() as progress:
        task = progress.add_task("[cyan]Checking job statuses...", total=len(job_ids))
        
        # Process jobs in batches to limit concurrency
        for i in range(0, len(job_ids), concurrency):
            batch = job_ids[i:i+concurrency]
            batch_tasks = [get_job_status(job_id) for job_id in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            progress.update(task, advance=len(batch))
    
    return results

def parse_job_status(job_result):
    """Extract relevant information from job status result."""
    if "error" in job_result:
        return {
            "job_id": job_result["job_id"],
            "state": "ERROR",
            "error": job_result["error"]
        }
    
    try:
        status = job_result["status"]
        state = status.get("State", {}).get("State", "UNKNOWN")
        
        result = {
            "job_id": job_result["job_id"],
            "state": state,
        }
        
        # Extract additional information if available
        if "Status" in status:
            result["execution_time"] = status["Status"].get("ExecutionTime", "N/A")
            
            if "PublishedResults" in status["Status"]:
                published = status["Status"]["PublishedResults"]
                if published:
                    result["published_results"] = published
        
        return result
    
    except Exception as e:
        logger.error(f"Error parsing job result for {job_result['job_id']}: {str(e)}")
        return {
            "job_id": job_result["job_id"],
            "state": "PARSE_ERROR",
            "error": str(e)
        }

def display_status_table(parsed_results):
    """Display job statuses in a table."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Job ID", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Execution Time", style="yellow")
    table.add_column("Additional Info", style="blue")
    
    for result in parsed_results:
        job_id = result["job_id"]
        state = result["state"]
        exec_time = result.get("execution_time", "N/A")
        
        # Gather additional info
        additional_info = []
        if "error" in result:
            additional_info.append(f"Error: {result['error']}")
        if "published_results" in result:
            additional_info.append(f"Results published: {len(result['published_results'])} items")
        
        additional = "\n".join(additional_info) if additional_info else "None"
        
        table.add_row(
            job_id,
            state,
            str(exec_time),
            additional
        )
    
    console.print(table)

def count_by_state(parsed_results):
    """Count jobs by state."""
    counts = {}
    for result in parsed_results:
        state = result["state"]
        counts[state] = counts.get(state, 0) + 1
    
    return counts

def main(args):
    # Load job IDs from file
    try:
        with open(args.job_ids_file, 'r') as f:
            job_ids = json.load(f)
        
        if not isinstance(job_ids, list):
            raise ValueError("Job IDs file must contain a JSON array of job IDs")
        
        logger.info(f"Loaded {len(job_ids)} job IDs from {args.job_ids_file}")
    
    except Exception as e:
        logger.error(f"Error loading job IDs file: {str(e)}")
        sys.exit(1)
    
    # Check job statuses
    results = asyncio.run(check_job_statuses(job_ids, args.concurrency))
    
    # Parse results
    parsed_results = [parse_job_status(result) for result in results]
    
    # Display results
    if args.summary:
        # Show summary only
        counts = count_by_state(parsed_results)
        console.print("[bold]Job Status Summary:[/bold]")
        
        summary_table = Table(show_header=True, header_style="bold")
        summary_table.add_column("State", style="cyan")
        summary_table.add_column("Count", style="green")
        summary_table.add_column("Percentage", style="yellow")
        
        total = len(parsed_results)
        for state, count in sorted(counts.items()):
            percentage = (count / total) * 100
            summary_table.add_row(
                state,
                str(count),
                f"{percentage:.1f}%"
            )
        
        console.print(summary_table)
    else:
        # Show full table
        display_status_table(parsed_results)
        
        # Also show summary
        counts = count_by_state(parsed_results)
        console.print("\n[bold]Summary:[/bold]")
        for state, count in sorted(counts.items()):
            console.print(f"  {state}: {count} jobs")
    
    # Save detailed results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Detailed results saved to {args.output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check status of Bacalhau jobs")
    parser.add_argument("job_ids_file", help="JSON file containing job IDs")
    parser.add_argument("--concurrency", type=int, default=10, 
                        help="Maximum number of concurrent status checks")
    parser.add_argument("--summary", action="store_true", 
                        help="Show only summary statistics")
    parser.add_argument("--output", type=str, 
                        help="Output file for detailed results (JSON)")
    
    args = parser.parse_args()
    main(args)