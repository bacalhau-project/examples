#!/usr/bin/env python3

import asyncio
import logging
import time
import argparse
import sys
import json
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
job_statuses = {}
console = Console()
table_update_event = asyncio.Event()
table_update_running = False
events_to_progress = []

class JobStatus:
    def __init__(self, job_id, index):
        self.job_id = job_id
        self.index = index
        self.status = "Submitted"
        self.detailed_status = "Waiting"
        self.submitted_time = time.time()
        self.elapsed_time = 0
    
    def combined_status(self):
        return f"{self.status} ({self.detailed_status})"


def make_job_table():
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.add_column("Index", width=8, style="cyan", no_wrap=True)
    table.add_column("Job ID", width=12, style="green", no_wrap=True)
    table.add_column("Status", width=20, style="yellow", no_wrap=True)
    table.add_column("Elapsed", width=10, justify="right", style="magenta", no_wrap=True)
    
    sorted_statuses = sorted(job_statuses.values(), key=lambda x: x.index)
    for status in sorted_statuses:
        table.add_row(
            str(status.index),
            status.job_id[:12],
            status.combined_status()[:20],
            f"{status.elapsed_time:.1f}s",
        )
    return table


def create_layout(progress, table):
    layout = Layout()
    progress_panel = Panel(
        progress,
        title="Job Progress",
        border_style="green",
        padding=(1, 1),
    )
    layout.split(
        Layout(progress_panel, size=5),
        Layout(table),
    )
    return layout


async def update_table(live, total_jobs):
    global table_update_running, events_to_progress, job_statuses
    if table_update_running:
        logger.debug("Table update already running. Exiting.")
        return

    try:
        table_update_running = True
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed} of {task.total}"),
            TimeElapsedColumn(),
            expand=True,
        )
        task = progress.add_task("Submitting Jobs", total=total_jobs)

        while not table_update_event.is_set() or events_to_progress:
            while events_to_progress:
                event = events_to_progress.pop(0)
                job_statuses[event.job_id] = event
                progress.update(task, completed=len(job_statuses))

            # Update elapsed time for all jobs
            current_time = time.time()
            for status in job_statuses.values():
                status.elapsed_time = current_time - status.submitted_time

            table = make_job_table()
            layout = create_layout(progress, table)
            live.update(layout)

            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"Error in update_table: {str(e)}")
    finally:
        table_update_running = False


async def submit_job(job_spec_file, index, batch_size, time_between_batches):
    try:
        if index > 0 and index % batch_size == 0:
            logger.info(f"Waiting {time_between_batches} seconds before submitting next batch")
            await asyncio.sleep(time_between_batches)
        
        cmd = ["bacalhau", "job", "run", "--wait=false", "--id-only", job_spec_file]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Error submitting job {index}: {stderr.decode()}")
            return None
        
        job_id = stdout.decode().strip()
        logger.info(f"Job {index} submitted with ID: {job_id}")
        
        job_status = JobStatus(job_id, index)
        events_to_progress.append(job_status)
        
        return job_id
    
    except Exception as e:
        logger.error(f"Exception when submitting job {index}: {str(e)}")
        return None


async def main(args):
    global events_to_progress, job_statuses
    
    logger.info(f"Starting job submission: {args.jobs} jobs, batch size: {args.batch_size}, "
                f"interval: {args.interval}s, job spec: {args.job_spec}")
    
    job_ids = []
    
    with Live(console=console, refresh_per_second=10) as live:
        update_table_task = asyncio.create_task(update_table(live, args.jobs))
        
        # Submit jobs
        tasks = []
        for i in range(args.jobs):
            task = asyncio.create_task(
                submit_job(args.job_spec, i+1, args.batch_size, args.interval)
            )
            tasks.append(task)
        
        job_ids = await asyncio.gather(*tasks)
        
        # Set table update event when all jobs are submitted
        table_update_event.set()
        await update_table_task
    
    # Print final status
    job_ids = [job_id for job_id in job_ids if job_id]
    logger.info(f"Job submission complete. Submitted {len(job_ids)} jobs.")
    
    # Save job IDs to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(job_ids, f)
        logger.info(f"Job IDs saved to {args.output}")
    
    # Print final table
    final_table = make_job_table()
    console.print(final_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit multiple jobs to Bacalhau")
    parser.add_argument("--jobs", type=int, default=10, help="Number of jobs to submit")
    parser.add_argument("--batch-size", type=int, default=20, help="Jobs per batch")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between batches")
    parser.add_argument("--job-spec", type=str, default="job.yaml", help="Job spec file path")
    parser.add_argument("--output", type=str, help="Output file for job IDs")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        logger.info("Job submission interrupted by user")
        sys.exit(1)