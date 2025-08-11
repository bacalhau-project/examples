#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sdk",
#     "rich",
# ]
# ///

import time
import base64
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs, workspace
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Initialize client
client = WorkspaceClient()

console.print("[bold blue]Databricks Auto Loader Restart[/bold blue]")
console.print("=" * 60)

# Upload the notebook
console.print("\n[yellow]1. Uploading updated notebook...[/yellow]")
try:
    with open("databricks-notebooks/flexible-autoloader.py", "r") as f:
        content = f.read()
    
    # Encode content to base64
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    client.workspace.import_(
        path="/Users/aronchick@gmail.com/demos/flexible-autoloader",
        content=encoded_content,
        format=workspace.ImportFormat.SOURCE,
        language=workspace.Language.PYTHON,
        overwrite=True
    )
    console.print("[green]✅ Notebook uploaded successfully[/green]")
except Exception as e:
    console.print(f"[red]❌ Upload failed: {e}[/red]")
    exit(1)

# Create and run a job
console.print("\n[yellow]2. Creating job to run notebook...[/yellow]")
try:
    job = client.jobs.create(
        name=f"AutoLoader-Restart-{int(time.time())}",
        tasks=[
            jobs.Task(
                task_key="run_autoloader",
                notebook_task=jobs.NotebookTask(
                    notebook_path="/Users/aronchick@gmail.com/demos/flexible-autoloader"
                ),
                existing_cluster_id="6a80650f34fb7115"
            )
        ],
        max_concurrent_runs=1
    )
    console.print(f"[green]✅ Job created: {job.job_id}[/green]")
    
    # Run the job
    console.print("\n[yellow]3. Starting job run...[/yellow]")
    run = client.jobs.run_now(job_id=job.job_id)
    console.print(f"[green]✅ Job started: Run ID {run.run_id}[/green]")
    
    # Monitor the run
    console.print("\n[yellow]4. Monitoring job execution...[/yellow]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Running notebook...", total=None)
        
        while True:
            run_info = client.jobs.get_run(run_id=run.run_id)
            state = run_info.state
            
            if state.life_cycle_state in ["TERMINATED", "SKIPPED", "INTERNAL_ERROR"]:
                break
                
            progress.update(task, description=f"Status: {state.life_cycle_state}")
            time.sleep(5)
    
    # Final status
    run_info = client.jobs.get_run(run_id=run.run_id)
    if run_info.state.result_state == "SUCCESS":
        console.print(f"\n[green]✅ Job completed successfully![/green]")
        console.print(f"[green]The Auto Loader pipelines have been restarted.[/green]")
        console.print(f"\n[cyan]View the job at:[/cyan]")
        console.print(f"[cyan]https://dbc-d5c2cb0e-3375.cloud.databricks.com/?o=2734650744297830#job/{job.job_id}/run/{run.run_id}[/cyan]")
    else:
        console.print(f"\n[red]❌ Job failed: {run_info.state.state_message}[/red]")
        
except Exception as e:
    console.print(f"[red]❌ Error: {e}[/red]")
    import traceback
    traceback.print_exc()
    exit(1)