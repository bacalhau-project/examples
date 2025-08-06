#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.0.0",
#     "python-dateutil>=2.8.0",
# ]
# ///
"""
Show upload status for all tables and pipeline executions.

Displays:
- Current pipeline configuration
- Upload state for each table
- Recent pipeline executions
- Total records uploaded
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from dateutil import parser
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


console = Console()


def load_upload_state(state_dir: Path) -> Dict[str, Any]:
    """Load upload state from JSON file."""
    state_file = state_dir / "s3-uploader" / "upload_state.json"
    if state_file.exists():
        with open(state_file, 'r') as f:
            return json.load(f)
    return {}


def get_pipeline_config(db_path: Path) -> Dict[str, Any]:
    """Get current pipeline configuration."""
    if not db_path.exists():
        return {"type": "Not configured", "source": "N/A", "created_at": "N/A"}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pipeline_type, created_at, created_by 
        FROM pipeline_config 
        WHERE is_active = 1
        ORDER BY id DESC 
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'type': result[0],
            'created_at': result[1],
            'source': result[2] or 'database'
        }
    return {"type": "raw (default)", "source": "default", "created_at": "N/A"}


def get_execution_history(db_path: Path, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent execution history."""
    if not db_path.exists():
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pipeline_type, records_processed, s3_locations, job_id, created_at
        FROM pipeline_executions
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'pipeline_type': row[0],
            'records_processed': row[1],
            's3_locations': json.loads(row[2]) if row[2] else [],
            'job_id': row[3],
            'created_at': row[4]
        })
    
    conn.close()
    return results


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display."""
    if not timestamp_str or timestamp_str == "N/A":
        return "N/A"
    try:
        dt = parser.parse(timestamp_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str


def format_time_ago(timestamp_str: str) -> str:
    """Format timestamp as time ago."""
    if not timestamp_str or timestamp_str == "N/A":
        return "N/A"
    try:
        dt = parser.parse(timestamp_str)
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        
        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return f"{delta.seconds}s ago"
    except:
        return timestamp_str


def main():
    """Display upload status."""
    # Find state directory
    state_dir = Path("state")
    if not state_dir.exists():
        console.print("[red]State directory not found![/red]")
        return
    
    # Load configurations
    pipeline_db = state_dir / "pipeline_config.db"
    upload_state = load_upload_state(state_dir)
    pipeline_config = get_pipeline_config(pipeline_db)
    execution_history = get_execution_history(pipeline_db)
    
    # Display header
    console.print(Panel.fit(
        "[bold blue]📊 Databricks S3 Upload Status[/bold blue]",
        box=box.DOUBLE
    ))
    
    # Current pipeline configuration
    console.print("\n[bold cyan]Current Pipeline Configuration:[/bold cyan]")
    config_table = Table(box=box.ROUNDED)
    config_table.add_column("Setting", style="yellow")
    config_table.add_column("Value", style="green")
    
    config_table.add_row("Pipeline Type", pipeline_config['type'])
    config_table.add_row("Configuration Source", pipeline_config['source'])
    config_table.add_row("Last Changed", format_timestamp(pipeline_config['created_at']))
    
    console.print(config_table)
    
    # Upload state
    console.print("\n[bold cyan]Upload State:[/bold cyan]")
    state_table = Table(box=box.ROUNDED)
    state_table.add_column("Metric", style="yellow")
    state_table.add_column("Value", style="green")
    
    if upload_state:
        state_table.add_row("Last Upload", format_timestamp(upload_state.get('last_upload', 'Never')))
        state_table.add_row("Time Ago", format_time_ago(upload_state.get('last_upload', 'Never')))
        state_table.add_row("Last Timestamp", upload_state.get('last_timestamp', 'N/A'))
        state_table.add_row("Total Records Uploaded", f"{upload_state.get('records_uploaded', 0):,}")
        state_table.add_row("Last Pipeline Used", upload_state.get('last_pipeline_type', 'N/A'))
    else:
        state_table.add_row("Status", "[red]No uploads yet[/red]")
    
    console.print(state_table)
    
    # Recent executions
    if execution_history:
        console.print("\n[bold cyan]Recent Pipeline Executions:[/bold cyan]")
        exec_table = Table(box=box.ROUNDED)
        exec_table.add_column("Time", style="blue")
        exec_table.add_column("Pipeline", style="yellow")
        exec_table.add_column("Records", style="green", justify="right")
        exec_table.add_column("Destination", style="magenta")
        
        for exec in execution_history[:10]:
            time_str = format_time_ago(exec['created_at'])
            destination = exec['s3_locations'][0] if exec['s3_locations'] else 'N/A'
            # Shorten S3 path for display
            if destination.startswith('s3://'):
                parts = destination.split('/')
                if len(parts) >= 4:
                    destination = f".../{parts[3]}/"
            
            exec_table.add_row(
                time_str,
                exec['pipeline_type'],
                f"{exec['records_processed']:,}",
                destination
            )
        
        console.print(exec_table)
    
    # Summary statistics
    if execution_history:
        console.print("\n[bold cyan]Summary Statistics:[/bold cyan]")
        
        # Calculate totals by pipeline type
        pipeline_totals = {}
        for exec in execution_history:
            ptype = exec['pipeline_type']
            if ptype not in pipeline_totals:
                pipeline_totals[ptype] = {'count': 0, 'records': 0}
            pipeline_totals[ptype]['count'] += 1
            pipeline_totals[ptype]['records'] += exec['records_processed']
        
        summary_table = Table(box=box.ROUNDED)
        summary_table.add_column("Pipeline Type", style="yellow")
        summary_table.add_column("Executions", style="blue", justify="right")
        summary_table.add_column("Total Records", style="green", justify="right")
        
        for ptype, stats in sorted(pipeline_totals.items()):
            summary_table.add_row(
                ptype,
                str(stats['count']),
                f"{stats['records']:,}"
            )
        
        console.print(summary_table)
    
    # Footer with commands
    console.print("\n[dim]Commands:[/dim]")
    console.print("[dim]• Change pipeline: uv run -s databricks-uploader/pipeline_manager.py --db state/pipeline_config.db set --type <type>[/dim]")
    console.print("[dim]• View history: uv run -s databricks-uploader/pipeline_manager.py --db state/pipeline_config.db history[/dim]")
    console.print("[dim]• Start uploader: uv run -s databricks-uploader/sqlite_to_databricks_uploader.py --config databricks-s3-uploader-config.yaml[/dim]")


if __name__ == "__main__":
    main()