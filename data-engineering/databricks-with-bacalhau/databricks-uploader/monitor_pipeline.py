#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich",
#     "click",
#     "pydantic",
# ]
# ///
"""Monitor pipeline execution history and health status."""

import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import time

from pipeline_manager import PipelineManager, PipelineExecution, PipelineType

console = Console()

def format_duration(start: datetime, end: Optional[datetime]) -> str:
    """Format duration between two timestamps."""
    if not end:
        end = datetime.now()
    duration = end - start
    
    if duration.days > 0:
        return f"{duration.days}d {duration.seconds // 3600}h"
    elif duration.seconds > 3600:
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    elif duration.seconds > 60:
        minutes = duration.seconds // 60
        seconds = duration.seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        return f"{duration.seconds}s"

def get_health_status(manager: PipelineManager, max_age_minutes: int = 30) -> Tuple[str, str]:
    """Determine health status based on recent executions."""
    history = manager.get_execution_history(limit=10)
    
    if not history:
        return "⚠️  NO DATA", "No executions found"
    
    latest = history[0]
    age = datetime.now() - latest.started_at
    
    # Check if latest execution is recent
    if age > timedelta(minutes=max_age_minutes):
        return "⚠️  STALE", f"Last execution {format_duration(latest.started_at, datetime.now())} ago"
    
    # Check if latest execution is still running
    if latest.status == "running":
        if age > timedelta(minutes=10):
            return "⚠️  STUCK", f"Execution running for {format_duration(latest.started_at, None)}"
        else:
            return "🔄 RUNNING", f"Execution in progress ({format_duration(latest.started_at, None)})"
    
    # Check recent failure rate
    recent_failures = sum(1 for exec in history[:5] if exec.status == "failed")
    if recent_failures >= 3:
        return "❌ FAILING", f"{recent_failures}/5 recent executions failed"
    elif recent_failures > 0:
        return "⚠️  UNSTABLE", f"{recent_failures}/5 recent executions failed"
    
    # All good
    return "✅ HEALTHY", "All systems operational"

def create_execution_table(executions: List[PipelineExecution], show_all: bool = False) -> Table:
    """Create a rich table showing execution history."""
    table = Table(title="Pipeline Execution History")
    
    table.add_column("ID", style="dim", width=6)
    table.add_column("Pipeline", style="cyan")
    table.add_column("Started", style="blue")
    table.add_column("Duration", justify="right")
    table.add_column("Records", justify="right", style="green")
    table.add_column("Status", justify="center")
    if show_all:
        table.add_column("Error", style="red")
    
    for exec in executions:
        # Format status with color
        if exec.status == "completed":
            status = Text("✓ Complete", style="green")
        elif exec.status == "failed":
            status = Text("✗ Failed", style="red")
        else:
            status = Text("⟳ Running", style="yellow")
        
        # Calculate duration
        duration = format_duration(exec.started_at, exec.completed_at)
        
        # Format start time
        start_time = exec.started_at.strftime("%H:%M:%S")
        if exec.started_at.date() != datetime.now().date():
            start_time = exec.started_at.strftime("%Y-%m-%d %H:%M")
        
        row = [
            str(exec.id),
            exec.pipeline_type.value if isinstance(exec.pipeline_type, PipelineType) else exec.pipeline_type,
            start_time,
            duration,
            str(exec.records_processed),
            status
        ]
        
        if show_all and exec.error_message:
            row.append(exec.error_message[:50] + "..." if len(exec.error_message) > 50 else exec.error_message)
        elif show_all:
            row.append("")
        
        table.add_row(*row)
    
    return table

def get_pipeline_stats(manager: PipelineManager, hours: int = 24) -> Dict[str, any]:
    """Get statistics for the last N hours."""
    since = datetime.now() - timedelta(hours=hours)
    
    # Get all executions (we'll filter by time)
    all_executions = manager.get_execution_history(limit=1000)
    recent_executions = [e for e in all_executions if e.started_at >= since]
    
    if not recent_executions:
        return {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "records_processed": 0,
            "avg_duration": "N/A",
            "by_pipeline": {}
        }
    
    # Calculate stats
    successful = [e for e in recent_executions if e.status == "completed"]
    failed = [e for e in recent_executions if e.status == "failed"]
    
    # Average duration for successful runs
    if successful:
        durations = [(e.completed_at - e.started_at).total_seconds() 
                    for e in successful if e.completed_at]
        avg_duration_seconds = sum(durations) / len(durations) if durations else 0
        avg_duration = f"{int(avg_duration_seconds)}s"
    else:
        avg_duration = "N/A"
    
    # Stats by pipeline type
    by_pipeline = {}
    for pipeline in PipelineType:
        pipeline_execs = [e for e in recent_executions 
                         if (e.pipeline_type == pipeline.value or e.pipeline_type == pipeline)]
        if pipeline_execs:
            by_pipeline[pipeline.value] = {
                "count": len(pipeline_execs),
                "records": sum(e.records_processed for e in pipeline_execs),
                "success_rate": len([e for e in pipeline_execs if e.status == "completed"]) / len(pipeline_execs) * 100
            }
    
    return {
        "total_executions": len(recent_executions),
        "successful": len(successful),
        "failed": len(failed),
        "records_processed": sum(e.records_processed for e in recent_executions),
        "avg_duration": avg_duration,
        "by_pipeline": by_pipeline
    }

@click.command()
@click.option('--db', required=True, help='Path to SQLite database')
@click.option('--watch', is_flag=True, help='Watch mode - refresh every 30 seconds')
@click.option('--limit', default=20, help='Number of executions to show')
@click.option('--show-all', is_flag=True, help='Show all details including errors')
@click.option('--stats-hours', default=24, help='Hours to include in statistics')
def main(db: str, watch: bool, limit: int, show_all: bool, stats_hours: int):
    """Monitor pipeline execution history and health."""
    
    if not Path(db).exists():
        console.print(f"[red]Error: Database not found: {db}[/red]")
        sys.exit(1)
    
    manager = PipelineManager(db)
    
    def render_dashboard():
        """Render the monitoring dashboard."""
        # Get current pipeline
        current_pipeline = manager.get_current_pipeline()
        
        # Get health status
        health_status, health_message = get_health_status(manager)
        
        # Get statistics
        stats = get_pipeline_stats(manager, hours=stats_hours)
        
        # Create header panel
        header_content = f"""[bold]Pipeline Status[/bold]
        
Current Pipeline: [cyan]{current_pipeline.pipeline_type.value}[/cyan]
Health Status: {health_status}
Message: {health_message}
Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        console.print(Panel(header_content, title="Databricks Pipeline Monitor"))
        
        # Statistics panel
        if stats['total_executions'] > 0:
            success_rate = (stats['successful'] / stats['total_executions']) * 100
            stats_content = f"""[bold]Last {stats_hours} Hours Statistics[/bold]
            
Total Executions: {stats['total_executions']}
Successful: [green]{stats['successful']}[/green] ({success_rate:.1f}%)
Failed: [red]{stats['failed']}[/red]
Records Processed: [cyan]{stats['records_processed']:,}[/cyan]
Avg Duration: {stats['avg_duration']}"""
            
            if stats['by_pipeline']:
                stats_content += "\n\n[bold]By Pipeline Type:[/bold]"
                for pipeline, pstats in stats['by_pipeline'].items():
                    stats_content += f"\n  {pipeline}: {pstats['count']} runs, {pstats['records']:,} records, {pstats['success_rate']:.0f}% success"
            
            console.print(Panel(stats_content, title="Statistics"))
        
        # Execution history table
        history = manager.get_execution_history(limit=limit)
        if history:
            table = create_execution_table(history, show_all=show_all)
            console.print(table)
        else:
            console.print("[yellow]No execution history found[/yellow]")
        
        # Show running executions separately
        running = [e for e in history if e.status == "running"]
        if running:
            console.print(f"\n[yellow]⚠️  {len(running)} execution(s) currently running[/yellow]")
    
    if watch:
        console.print("[dim]Watching pipeline... Press Ctrl+C to exit[/dim]\n")
        try:
            while True:
                console.clear()
                render_dashboard()
                time.sleep(30)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped watching[/dim]")
    else:
        render_dashboard()

if __name__ == "__main__":
    main()