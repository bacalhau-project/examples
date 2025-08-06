#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "rich",
#     "python-dotenv",
# ]
# ///
"""
Databricks S3 Infrastructure Setup and Verification

Central command-line interface for setting up and verifying the infrastructure
required for the Databricks uploader containers.

Usage:
    uv run -s setup.py --help
    uv run -s setup.py all
    uv run -s setup.py verify
    uv run -s setup.py test-s3
"""

import subprocess
import sys
import os
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from dotenv import load_dotenv

console = Console()

# Load environment variables from .env file
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Get script directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

def run_command(cmd, description=None, cwd=None):
    """Run a command and display output"""
    if description:
        console.print(f"[bold blue]→[/bold blue] {description}")
    
    if isinstance(cmd, str):
        cmd = cmd.split()
    
    try:
        result = subprocess.run(cmd, cwd=cwd or SCRIPT_DIR, 
                              capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]✓[/green] Success")
            if result.stdout:
                console.print(result.stdout)
            return True
        else:
            console.print(f"[red]✗[/red] Failed")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        return False

@click.group()
def cli():
    """Databricks S3 Infrastructure Setup"""
    pass

@cli.command(name='all')
def setup_all():
    """Complete infrastructure setup (S3, IAM, Databricks)"""
    console.print(Panel.fit("🏗️  Databricks S3 Infrastructure Setup", style="bold magenta"))
    
    steps = [
        ("Creating S3 buckets", "./create-s3-buckets.sh --prefix expanso --region us-west-2"),
        ("Updating IAM role policy", "./update-iam-role-policy-west.sh"),
        ("Configuring Databricks access", "uv run -s databricks-setup-and-test.py"),
    ]
    
    for description, cmd in steps:
        if not run_command(cmd, description):
            console.print(f"[yellow]Warning: {description} had issues but continuing...[/yellow]")
    
    console.print("\n[green]✅ Infrastructure setup complete![/green]")
    console.print("\nNext: Run 'uv run -s setup.py verify' to test the setup")

@cli.command()
def verify():
    """Verify all infrastructure is working"""
    console.print(Panel.fit("🔍 Verifying Infrastructure", style="bold cyan"))
    
    # Check S3 buckets
    run_command("./check-s3-buckets-west.sh", "Checking S3 buckets exist")
    
    # Test S3 configuration
    run_command("uv run -s test-s3-uploader-west.py", "Testing S3 configuration")
    
    console.print("\n[bold]To test Databricks S3 access, run:[/bold]")
    console.print("  uv run -s setup.py test-s3")

@cli.command(name='test-s3')
def test_s3():
    """Test Databricks S3 read/write/delete access"""
    console.print(Panel.fit("🧪 Testing Databricks S3 Access", style="bold yellow"))
    run_command("uv run -s test-databricks-s3-access.py", "Running comprehensive S3 tests")

@cli.command()
def buckets():
    """Check S3 bucket status"""
    console.print(Panel.fit("🪣 S3 Bucket Status", style="bold blue"))
    
    # Check if buckets exist
    run_command("./check-s3-buckets-west.sh", "Checking S3 buckets")
    
    # Query bucket contents
    run_command("uv run -s query-s3-buckets.py", "Querying bucket contents")

@cli.command()
def databricks():
    """Test Databricks configuration"""
    console.print(Panel.fit("📊 Databricks Configuration Test", style="bold yellow"))
    
    # Test authentication
    cmd = ["databricks", "workspace", "list", "/"]
    env = os.environ.copy()
    env["DATABRICKS_CLI_DO_NOT_EXECUTE_NEWER_VERSION"] = "1"
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        console.print("[green]✅ Databricks authentication working[/green]")
        console.print(f"   Host: {os.environ.get('DATABRICKS_HOST', 'Not set')}")
    else:
        console.print("[red]❌ Databricks authentication failed[/red]")
        console.print("   Please check your .env file or run:")
        console.print("   databricks configure --token")

@cli.command()
def aws():
    """Test AWS credentials and configuration"""
    console.print(Panel.fit("☁️  AWS Configuration Test", style="bold cyan"))
    
    # Import here to avoid dependency issues
    try:
        from aws_error_handler import test_aws_credentials
    except ImportError:
        console.print("[yellow]Running inline AWS test...[/yellow]")
        # Inline test if import fails
        cmd = ["aws", "sts", "get-caller-identity", "--no-cli-pager"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        
        if result.returncode == 0:
            import json
            try:
                info = json.loads(result.stdout)
                console.print("[green]✅ AWS credentials valid[/green]")
                console.print(f"   Account: {info.get('Account', 'Unknown')}")
                console.print(f"   User/Role: {info.get('Arn', '').split('/')[-1]}")
            except:
                console.print("[green]✅ AWS CLI working[/green]")
                console.print(result.stdout)
        else:
            console.print("[red]❌ AWS authentication failed[/red]")
            if "ExpiredToken" in result.stderr:
                console.print("\n[yellow]Token expired. Run:[/yellow]")
                console.print("   aws sso login")
            elif "Unable to locate credentials" in result.stderr:
                console.print("\n[yellow]No credentials found. Run:[/yellow]")
                console.print("   aws configure")
            else:
                console.print(f"\n[dim]{result.stderr}[/dim]")
        return
    
    # Use the error handler if available
    test_aws_credentials()

@cli.command()
@click.option('--prefix', default='expanso', help='S3 bucket prefix')
@click.option('--regions', default='us-east-1,us-west-2,eu-west-1,ap-southeast-1', help='Comma-separated regions')
def regional(prefix, regions):
    """Set up regional S3 buckets and test regional scenario"""
    console.print(Panel.fit("🌎 Regional Infrastructure Setup", style="bold magenta"))
    
    # Create regional buckets
    console.print("\n[cyan]Creating regional S3 buckets...[/cyan]")
    result = subprocess.run([
        "bash", "create-regional-s3-buckets.sh", prefix, regions.replace(',', ' ')
    ], cwd=SCRIPT_DIR)
    
    if result.returncode != 0:
        console.print("[red]❌ Failed to create regional buckets[/red]")
        sys.exit(1)
    
    # Update IAM role policy
    console.print("\n[cyan]Updating IAM role policy for regional access...[/cyan]")
    result = subprocess.run([
        "bash", "update-iam-role-policy-regional.sh", prefix, regions.replace(',', ' ')
    ], cwd=SCRIPT_DIR)
    
    if result.returncode != 0:
        console.print("[red]❌ Failed to update IAM policy[/red]")
        sys.exit(1)
    
    # Test regional scenario
    console.print("\n[cyan]Testing regional scenario...[/cyan]")
    result = subprocess.run([
        "uv", "run", "-s",
        "test-regional-scenario.py",
        "--prefix", prefix,
        "--test-regions", regions
    ], cwd=SCRIPT_DIR)
    
    if result.returncode != 0:
        console.print("[red]❌ Regional test failed[/red]")
        sys.exit(1)
    
    console.print("\n[green]✅ Regional setup complete![/green]")
    console.print("\nNext steps:")
    console.print("1. Run the regional external locations notebook in Databricks")
    console.print("2. Start uploading data with pipeline_type='regional'")
    console.print("3. Query cross-region data using the views")

@cli.command()
def help():
    """Show available commands"""
    table = Table(title="🛠️  Setup Commands", show_header=True)
    table.add_column("Command", style="cyan", width=20)
    table.add_column("Description", style="white")
    table.add_column("Example", style="green")
    
    commands = [
        ("all", "Complete infrastructure setup", "uv run -s setup.py all"),
        ("verify", "Verify infrastructure is working", "uv run -s setup.py verify"),
        ("test-s3", "Test Databricks S3 access", "uv run -s setup.py test-s3"),
        ("buckets", "Check S3 bucket status", "uv run -s setup.py buckets"),
        ("databricks", "Test Databricks CLI config", "uv run -s setup.py databricks"),
        ("regional", "Set up regional buckets", "uv run -s setup.py regional"),
    ]
    
    for cmd, desc, example in commands:
        table.add_row(cmd, desc, example)
    
    console.print(table)
    
    console.print("\n[bold]Setup Flow:[/bold]")
    console.print("1. Run [cyan]uv run -s setup.py all[/cyan] to create infrastructure")
    console.print("2. Run [cyan]uv run -s setup.py verify[/cyan] to check everything")
    console.print("3. Run [cyan]uv run -s setup.py test-s3[/cyan] to test Databricks access")
    console.print("4. (Optional) Run [cyan]uv run -s setup.py regional[/cyan] for multi-region setup")
    console.print("\n[bold]After setup:[/bold]")
    console.print("Your containers can use the databricks-uploader with S3 access!")

if __name__ == "__main__":
    cli()