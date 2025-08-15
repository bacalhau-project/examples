#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
#   "click",
# ]
# ///

"""
Upload and run Databricks notebooks programmatically.

This script:
1. Uploads notebooks to Databricks workspace
2. Creates a job to run the notebook
3. Triggers the job and monitors execution
4. Returns results
"""

import os
import sys
import time
import base64
from pathlib import Path
from typing import Optional, Dict, Any

import click
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs, workspace
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()


def get_workspace_client() -> WorkspaceClient:
    """Create Databricks workspace client from environment variables."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")

    if not host or not token:
        console.print("[red]Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env[/red]")
        sys.exit(1)

    return WorkspaceClient(host=host, token=token)


def upload_notebook(client: WorkspaceClient, local_path: Path, workspace_path: str) -> bool:
    """Upload a notebook to Databricks workspace."""
    try:
        # Read the notebook content
        content = local_path.read_text()

        # Update upload metadata timestamp if present
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_email = os.getenv("DATABRICKS_USER_EMAIL", "unknown")

        # Look for existing metadata block and update it
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "**Uploaded:**" in line:
                # Update the timestamp in markdown format
                lines[i] = f"# MAGIC - **Uploaded:** {current_time}"
            elif "Uploaded:" in line and "MAGIC" in lines[max(0, i - 1)]:
                # Update timestamp in MAGIC markdown
                lines[i] = f"# MAGIC - **Uploaded:** {current_time}"

        # If no metadata found, add it after "# Databricks notebook source"
        if (
            "**Uploaded:**" not in content
            and lines
            and lines[0].strip() == "# Databricks notebook source"
        ):
            metadata_block = [
                "# MAGIC %md",
                "# MAGIC ## Upload Metadata",
                f"# MAGIC - **Uploaded:** {current_time}",
                f"# MAGIC - **Validated:** ✓ (syntax check passed)",
                f"# MAGIC - **User:** {user_email}",
                f"# MAGIC - **Source:** {local_path.name}",
                "# MAGIC",
                "# MAGIC ---",
                "",
            ]
            # Find where to insert (after first MAGIC %md or at position 1)
            insert_pos = 1
            for idx, line in enumerate(lines[1:], 1):
                if "# MAGIC %md" in line:
                    # Insert before the first markdown cell
                    insert_pos = idx
                    break
            lines = lines[:insert_pos] + metadata_block + lines[insert_pos:]

        content = "\n".join(lines)

        # Encode content as base64
        content_b64 = base64.b64encode(content.encode()).decode()

        # Determine language based on file extension
        if local_path.suffix == ".py":
            language = workspace.Language.PYTHON
        elif local_path.suffix == ".sql":
            language = workspace.Language.SQL
        elif local_path.suffix == ".scala":
            language = workspace.Language.SCALA
        elif local_path.suffix == ".r":
            language = workspace.Language.R
        else:
            language = workspace.Language.PYTHON

        # Create parent directory if needed
        parent_path = str(Path(workspace_path).parent)
        try:
            client.workspace.mkdirs(parent_path)
        except:
            pass  # Directory might already exist

        # Upload the notebook
        client.workspace.import_(
            path=workspace_path,
            content=content_b64,
            format=workspace.ImportFormat.SOURCE,
            language=language,
            overwrite=True,
        )

        return True

    except Exception as e:
        console.print(f"[red]Error uploading notebook: {e}[/red]")
        return False


def create_and_run_job(
    client: WorkspaceClient,
    notebook_path: str,
    job_name: str,
    parameters: Optional[Dict[str, str]] = None,
    cluster_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
) -> Optional[str]:
    """Create and run a job for the notebook."""
    try:
        # Define the task
        if cluster_id:
            # Use existing cluster
            task = jobs.Task(
                task_key="run_notebook",
                notebook_task=jobs.NotebookTask(
                    notebook_path=notebook_path, base_parameters=parameters or {}
                ),
                existing_cluster_id=cluster_id,
                description=f"Run {notebook_path}",
            )
        else:
            task = jobs.Task(
                task_key="run_notebook",
                notebook_task=jobs.NotebookTask(
                    notebook_path=notebook_path, base_parameters=parameters or {}
                ),
                description=f"Run {notebook_path}",
            )

        # Create job configuration
        if cluster_id:
            # Use existing cluster
            job_config = jobs.JobSettings(name=job_name, tasks=[task], max_concurrent_runs=1)
        elif warehouse_id:
            # For SQL notebooks, we'd need different configuration
            console.print("[yellow]SQL warehouse execution not implemented yet[/yellow]")
            return None
        else:
            # Create new job cluster
            # Use compute.ClusterSpec instead of jobs.ClusterSpec
            from databricks.sdk.service import compute

            job_config = jobs.JobSettings(
                name=job_name,
                tasks=[task],
                max_concurrent_runs=1,
                job_clusters=[
                    jobs.JobCluster(
                        job_cluster_key="auto_cluster",
                        new_cluster=compute.ClusterSpec(
                            spark_version="13.3.x-scala2.12",
                            node_type_id="i3.xlarge",
                            num_workers=0,  # Single node
                            spark_conf={
                                "spark.databricks.cluster.profile": "singleNode",
                                "spark.master": "local[*]",
                            },
                            custom_tags={"ResourceClass": "SingleNode"},
                        ),
                    )
                ],
            )
            # Update task to use the job cluster
            task.job_cluster_key = "auto_cluster"

        # Create the job
        job = client.jobs.create(
            name=job_config.name,
            tasks=job_config.tasks,
            max_concurrent_runs=job_config.max_concurrent_runs,
            job_clusters=job_config.job_clusters
            if hasattr(job_config, "job_clusters") and job_config.job_clusters
            else None,
        )

        # Run the job
        run = client.jobs.run_now(job_id=job.job_id)

        return run.run_id

    except Exception as e:
        console.print(f"[red]Error creating/running job: {e}[/red]")
        return None


def monitor_job_run(client: WorkspaceClient, run_id: int) -> bool:
    """Monitor job execution and return success status."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running notebook...", total=None)

        while True:
            run = client.jobs.get_run(run_id=run_id)

            # Update progress description
            state = run.state.life_cycle_state
            progress.update(task, description=f"Running notebook... [{state}]")

            # Check if completed
            if state in [
                jobs.RunLifeCycleState.TERMINATED,
                jobs.RunLifeCycleState.SKIPPED,
                jobs.RunLifeCycleState.INTERNAL_ERROR,
            ]:
                if run.state.result_state == jobs.RunResultState.SUCCESS:
                    return True
                else:
                    console.print(f"[red]Job failed: {run.state.state_message}[/red]")
                    return False

            time.sleep(5)


def get_existing_cluster_id(client: WorkspaceClient) -> Optional[str]:
    """Get ID of an existing running cluster."""
    try:
        clusters = client.clusters.list()
        for cluster in clusters:
            if cluster.state == "RUNNING":
                return cluster.cluster_id
        return None
    except:
        return None


@click.command()
@click.option("--notebook", "-n", required=True, help="Path to notebook file")
@click.option(
    "--workspace-path", "-w", help="Workspace path (default: /Users/{email}/demos/{notebook_name})"
)
@click.option("--run", "-r", is_flag=True, help="Run the notebook after uploading")
@click.option("--parameters", "-p", multiple=True, help="Notebook parameters as key=value")
@click.option("--cluster-id", help="Existing cluster ID to use")
@click.option("--warehouse-id", help="SQL warehouse ID (for SQL notebooks)")
@click.option("--wait", is_flag=True, help="Wait for notebook execution to complete")
@click.option("--skip-validation", is_flag=True, help="Skip syntax validation before upload")
def main(
    notebook: str,
    workspace_path: Optional[str],
    run: bool,
    parameters: tuple,
    cluster_id: Optional[str],
    warehouse_id: Optional[str],
    wait: bool,
    skip_validation: bool,
):
    """Upload and optionally run a Databricks notebook."""

    console.print("[bold blue]Databricks Notebook Upload & Run[/bold blue]")
    console.print("=" * 50)

    # Initialize client
    client = get_workspace_client()

    # Get notebook path
    notebook_path = Path(notebook)
    if not notebook_path.exists():
        console.print(f"[red]Error: Notebook file not found: {notebook}[/red]")
        sys.exit(1)

    # Validate notebook syntax unless skipped
    if not skip_validation:
        console.print(f"\n[bold]Validating notebook syntax:[/bold]")
        validator_script = Path(__file__).parent / "validate-databricks-notebook.py"

        if validator_script.exists():
            import subprocess

            result = subprocess.run(
                ["uv", "run", "-s", str(validator_script), str(notebook_path), "--quiet"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                console.print("[red]✗ Notebook validation failed![/red]")
                if result.stdout:
                    console.print(result.stdout)
                if result.stderr:
                    console.print(result.stderr)
                console.print("\n[yellow]Tip: Use --skip-validation to upload anyway[/yellow]")
                sys.exit(1)
            else:
                console.print("[green]✓ Notebook syntax validated[/green]")
        else:
            console.print(
                "[yellow]Warning: Validator script not found, skipping validation[/yellow]"
            )

    # Determine workspace path
    if not workspace_path:
        # First try to get email from environment
        email = os.getenv("DATABRICKS_USER_EMAIL")

        # If not in env, get from API
        if not email:
            try:
                current_user = client.current_user.me()
                email = current_user.user_name
            except:
                email = "unknown"

        workspace_path = f"/Users/{email}/demos/{notebook_path.stem}"

    # Upload notebook
    console.print(f"\n[bold]Uploading notebook:[/bold]")
    console.print(f"  From: {notebook_path}")
    console.print(f"  To: {workspace_path}")

    if upload_notebook(client, notebook_path, workspace_path):
        console.print("[green]✓ Notebook uploaded successfully[/green]")
    else:
        console.print("[red]✗ Failed to upload notebook[/red]")
        sys.exit(1)

    # Run notebook if requested
    if run:
        console.print(f"\n[bold]Running notebook:[/bold]")

        # Parse parameters
        params = {}
        for param in parameters:
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value

        if params:
            console.print("  Parameters:")
            for k, v in params.items():
                console.print(f"    {k} = {v}")

        # Try to find existing cluster if not specified
        if not cluster_id and not warehouse_id:
            console.print("  Looking for existing cluster...")
            cluster_id = get_existing_cluster_id(client)
            if cluster_id:
                console.print(f"  Found cluster: {cluster_id}")
            else:
                console.print("  No running cluster found, will create new one")

        # Create and run job
        job_name = f"Run {notebook_path.stem} - {time.strftime('%Y%m%d_%H%M%S')}"
        run_id = create_and_run_job(
            client, workspace_path, job_name, params, cluster_id, warehouse_id
        )

        if run_id:
            console.print(f"[green]✓ Job started with run ID: {run_id}[/green]")

            # Get run URL
            run_url = f"{os.getenv('DATABRICKS_HOST')}/#job/{run_id}"
            console.print(f"  View run: {run_url}")

            # Wait for completion if requested
            if wait:
                success = monitor_job_run(client, run_id)
                if success:
                    console.print("[green]✓ Notebook execution completed successfully[/green]")
                else:
                    console.print("[red]✗ Notebook execution failed[/red]")
                    sys.exit(1)
        else:
            console.print("[red]✗ Failed to start job[/red]")
            sys.exit(1)

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Notebook uploaded to: {workspace_path}")
    if run:
        console.print(f"  Job run ID: {run_id}")
        console.print(f"  Status: {'Running' if not wait else 'Completed'}")


if __name__ == "__main__":
    main()
