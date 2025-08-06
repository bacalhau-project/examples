#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.0.0",
#     "click>=8.0.0",
#     "watchdog>=2.0.0"
# ]
# ///

"""
Real-time Log Monitor for Pipeline

Monitors log files in real-time and provides:
- Live error tracking
- Performance metrics
- Alert notifications
- Log search and filtering
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict, deque

import click
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class LogFileHandler(FileSystemEventHandler):
    """Handles log file changes."""
    
    def __init__(self, monitor):
        self.monitor = monitor
        self.file_positions = {}
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
            
        filepath = Path(event.src_path)
        if filepath.suffix in ['.log', '.json']:
            self.monitor.process_file_update(filepath)


class LogMonitor:
    """Real-time log monitor."""
    
    def __init__(self, log_dir: str = "logs", 
                 error_threshold: int = 10,
                 window_minutes: int = 5):
        """Initialize the log monitor.
        
        Args:
            log_dir: Directory to monitor
            error_threshold: Error count threshold for alerts
            window_minutes: Time window for error counting
        """
        self.log_dir = Path(log_dir)
        self.error_threshold = error_threshold
        self.window_minutes = window_minutes
        
        self.console = Console()
        
        # State tracking
        self.errors = deque(maxlen=1000)
        self.warnings = deque(maxlen=1000)
        self.metrics = defaultdict(list)
        self.performance = defaultdict(list)
        self.file_positions = {}
        
        # Alert tracking
        self.alerts = []
        self.alert_cooldown = {}
        
        # File handler
        self.handler = LogFileHandler(self)
        self.observer = Observer()
    
    def start_monitoring(self):
        """Start monitoring log files."""
        # Initial scan
        self.scan_existing_logs()
        
        # Start file watcher
        self.observer.schedule(self.handler, str(self.log_dir), recursive=True)
        self.observer.start()
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.observer.stop()
        self.observer.join()
    
    def scan_existing_logs(self):
        """Scan existing log files."""
        for log_file in self.log_dir.glob("**/*.log"):
            self.process_file_update(log_file)
    
    def process_file_update(self, filepath: Path):
        """Process updates to a log file."""
        # Get last position
        last_pos = self.file_positions.get(str(filepath), 0)
        
        try:
            with open(filepath, 'r') as f:
                # Seek to last position
                f.seek(last_pos)
                
                # Read new lines
                for line in f:
                    self.process_log_line(line, filepath)
                
                # Update position
                self.file_positions[str(filepath)] = f.tell()
        except Exception as e:
            self.console.print(f"[red]Error reading {filepath}: {e}[/red]")
    
    def process_log_line(self, line: str, source: Path):
        """Process a single log line."""
        try:
            # Try to parse as JSON
            if line.strip().startswith('{'):
                data = json.loads(line)
                self.process_json_log(data, source)
            else:
                # Parse text log
                self.process_text_log(line, source)
        except:
            # Ignore parse errors
            pass
    
    def process_json_log(self, data: Dict[str, Any], source: Path):
        """Process JSON formatted log."""
        timestamp = data.get('timestamp', datetime.now().isoformat())
        level = data.get('level', 'INFO')
        
        # Track errors and warnings
        if level == 'ERROR' or level == 'CRITICAL':
            self.errors.append({
                'timestamp': timestamp,
                'message': data.get('message', ''),
                'source': source.name,
                'data': data
            })
            self.check_alerts()
        elif level == 'WARNING':
            self.warnings.append({
                'timestamp': timestamp,
                'message': data.get('message', ''),
                'source': source.name,
                'data': data
            })
        
        # Track metrics
        if 'metric_name' in data:
            self.metrics[data['metric_name']].append({
                'timestamp': timestamp,
                'value': data.get('value', 0),
                'tags': data.get('tags', {})
            })
        
        # Track performance
        if 'performance_type' in data:
            self.performance[data.get('operation', 'unknown')].append({
                'timestamp': timestamp,
                'duration': data.get('duration_seconds', 0),
                'records': data.get('records', 0)
            })
    
    def process_text_log(self, line: str, source: Path):
        """Process text formatted log."""
        # Simple pattern matching
        if 'ERROR' in line or 'CRITICAL' in line:
            self.errors.append({
                'timestamp': datetime.now().isoformat(),
                'message': line.strip(),
                'source': source.name,
                'data': {}
            })
            self.check_alerts()
        elif 'WARNING' in line:
            self.warnings.append({
                'timestamp': datetime.now().isoformat(),
                'message': line.strip(),
                'source': source.name,
                'data': {}
            })
    
    def check_alerts(self):
        """Check if alerts should be triggered."""
        # Count recent errors
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        recent_errors = [
            e for e in self.errors 
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]
        
        if len(recent_errors) >= self.error_threshold:
            alert_key = f"error_threshold_{len(recent_errors)}"
            
            # Check cooldown
            if alert_key not in self.alert_cooldown or \
               datetime.now() > self.alert_cooldown[alert_key]:
                
                self.alerts.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error_threshold',
                    'message': f"Error threshold exceeded: {len(recent_errors)} errors in {self.window_minutes} minutes",
                    'severity': 'high'
                })
                
                # Set cooldown
                self.alert_cooldown[alert_key] = datetime.now() + timedelta(minutes=5)
    
    def get_dashboard_layout(self) -> Layout:
        """Create dashboard layout."""
        layout = Layout()
        
        # Create sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Split main section
        layout["main"].split_row(
            Layout(name="errors"),
            Layout(name="metrics")
        )
        
        # Header
        layout["header"].update(
            Panel(
                Text("Pipeline Log Monitor", style="bold blue", justify="center"),
                border_style="blue"
            )
        )
        
        # Errors section
        error_table = Table(title="Recent Errors")
        error_table.add_column("Time", style="cyan")
        error_table.add_column("Source", style="yellow")
        error_table.add_column("Message", style="red")
        
        for error in list(self.errors)[-10:]:
            timestamp = datetime.fromisoformat(error['timestamp'])
            error_table.add_row(
                timestamp.strftime("%H:%M:%S"),
                error['source'],
                error['message'][:80] + "..." if len(error['message']) > 80 else error['message']
            )
        
        layout["errors"].update(Panel(error_table, title="Errors & Warnings"))
        
        # Metrics section
        metrics_table = Table(title="Performance Metrics")
        metrics_table.add_column("Operation", style="cyan")
        metrics_table.add_column("Count", style="green")
        metrics_table.add_column("Avg Duration", style="yellow")
        metrics_table.add_column("Records/sec", style="magenta")
        
        for op, perfs in self.performance.items():
            if perfs:
                recent_perfs = perfs[-100:]  # Last 100
                avg_duration = sum(p['duration'] for p in recent_perfs) / len(recent_perfs)
                total_records = sum(p.get('records', 0) for p in recent_perfs)
                total_duration = sum(p['duration'] for p in recent_perfs)
                
                metrics_table.add_row(
                    op,
                    str(len(recent_perfs)),
                    f"{avg_duration:.2f}s",
                    f"{total_records / total_duration:.0f}" if total_duration > 0 else "0"
                )
        
        layout["metrics"].update(Panel(metrics_table, title="Performance"))
        
        # Footer with alerts
        if self.alerts:
            latest_alert = self.alerts[-1]
            alert_text = Text(
                f"⚠️  {latest_alert['message']}", 
                style="bold red"
            )
        else:
            alert_text = Text("✓ No active alerts", style="green")
        
        layout["footer"].update(Panel(alert_text, title="Alerts"))
        
        return layout
    
    def search_logs(self, pattern: str, 
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Search logs for pattern.
        
        Args:
            pattern: Search pattern (regex)
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            List of matching log entries
        """
        matches = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        # Search all log files
        for log_file in self.log_dir.glob("**/*.log"):
            with open(log_file, 'r') as f:
                for line in f:
                    if regex.search(line):
                        # Parse timestamp if possible
                        timestamp = None
                        try:
                            if line.startswith('{'):
                                data = json.loads(line)
                                timestamp = datetime.fromisoformat(data.get('timestamp'))
                        except:
                            pass
                        
                        # Apply time filters
                        if timestamp:
                            if start_time and timestamp < start_time:
                                continue
                            if end_time and timestamp > end_time:
                                continue
                        
                        matches.append({
                            'file': log_file.name,
                            'line': line.strip(),
                            'timestamp': timestamp
                        })
        
        return matches


@click.group()
def cli():
    """Pipeline log monitor CLI."""
    pass


@cli.command()
@click.option('--log-dir', default='logs', help='Log directory to monitor')
@click.option('--error-threshold', default=10, help='Error threshold for alerts')
@click.option('--window-minutes', default=5, help='Time window for error counting')
def monitor(log_dir: str, error_threshold: int, window_minutes: int):
    """Start real-time log monitoring."""
    monitor = LogMonitor(log_dir, error_threshold, window_minutes)
    monitor.start_monitoring()
    
    console = Console()
    console.print("[green]Starting log monitor...[/green]")
    console.print(f"Monitoring directory: {log_dir}")
    console.print(f"Error threshold: {error_threshold} errors in {window_minutes} minutes")
    console.print("\nPress Ctrl+C to stop")
    
    try:
        with Live(monitor.get_dashboard_layout(), refresh_per_second=1) as live:
            while True:
                time.sleep(1)
                live.update(monitor.get_dashboard_layout())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping monitor...[/yellow]")
        monitor.stop_monitoring()


@cli.command()
@click.option('--log-dir', default='logs', help='Log directory')
@click.argument('pattern')
@click.option('--start', help='Start time (ISO format)')
@click.option('--end', help='End time (ISO format)')
def search(log_dir: str, pattern: str, start: Optional[str], end: Optional[str]):
    """Search logs for pattern."""
    monitor = LogMonitor(log_dir)
    
    # Parse times
    start_time = datetime.fromisoformat(start) if start else None
    end_time = datetime.fromisoformat(end) if end else None
    
    # Search
    console = Console()
    console.print(f"[cyan]Searching for: {pattern}[/cyan]")
    
    matches = monitor.search_logs(pattern, start_time, end_time)
    
    if matches:
        console.print(f"\n[green]Found {len(matches)} matches:[/green]\n")
        
        for match in matches[:50]:  # Show first 50
            console.print(f"[yellow]{match['file']}:[/yellow] {match['line']}")
            
        if len(matches) > 50:
            console.print(f"\n[dim]... and {len(matches) - 50} more[/dim]")
    else:
        console.print("[red]No matches found[/red]")


@cli.command()
@click.option('--log-dir', default='logs', help='Log directory')
@click.option('--hours', default=24, help='Hours to analyze')
def analyze(log_dir: str, hours: int):
    """Analyze recent logs."""
    from pipeline_logging import LogAggregator
    
    console = Console()
    console.print(f"[cyan]Analyzing logs from last {hours} hours...[/cyan]\n")
    
    aggregator = LogAggregator(log_dir)
    
    # Error analysis
    error_analysis = aggregator.analyze_errors(hours)
    
    error_table = Table(title="Error Analysis")
    error_table.add_column("Metric", style="cyan")
    error_table.add_column("Value", style="red")
    
    error_table.add_row("Total Errors", str(error_analysis['total_errors']))
    error_table.add_row("Time Range", error_analysis['time_range'])
    
    if error_analysis['error_types']:
        error_table.add_row("Top Error Types", "")
        for error_type, count in sorted(
            error_analysis['error_types'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]:
            error_table.add_row(f"  {error_type}", str(count))
    
    console.print(error_table)
    
    # Performance metrics
    perf_metrics = aggregator.get_performance_metrics()
    
    if perf_metrics:
        perf_table = Table(title="Performance Metrics")
        perf_table.add_column("Metric", style="cyan")
        perf_table.add_column("Value", style="green")
        
        for metric, value in sorted(perf_metrics.items()):
            perf_table.add_row(metric, f"{value:,.2f}")
        
        console.print("\n")
        console.print(perf_table)


if __name__ == "__main__":
    cli()