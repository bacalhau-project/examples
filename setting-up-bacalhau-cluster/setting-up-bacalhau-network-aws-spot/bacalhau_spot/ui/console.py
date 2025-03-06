"""
Console UI module for rich terminal display.

This module provides a rich terminal interface for displaying status,
progress, and logs in a user-friendly way.
"""

import asyncio
import logging
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TaskProgressColumn,
                          TextColumn, TimeElapsedColumn)
from rich.table import Table, box

from ..utils.models import ErrorType, InstanceStatus

# Terminal width detection
console = Console()

# Configure logger for this module
logger = logging.getLogger(__name__)


class DisplayState:
    """Singleton class to store display state."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DisplayState, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the display state."""
        self.task_name = "Starting..."
        self.task_total = 100
        self.all_statuses: Dict[str, InstanceStatus] = {}
        self.event_ids: Set[str] = set()
        self.status_lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self.display_task: Optional[asyncio.Task] = None
        self.json_result: Optional[str] = None
        self.error_types: Dict[str, bool] = {
            "credential_issues": False,
            "capacity_issues": False,
            "price_issues": False,
            "config_issues": False,
            "network_issues": False,
        }
        
    async def add_status(self, status: InstanceStatus) -> None:
        """
        Add or update a status in the display.
        
        Args:
            status: Status to add or update
        """
        async with self.status_lock:
            self.all_statuses[status.id] = status
            self.event_ids.add(status.id)
    
    def reset(self) -> None:
        """Reset the display state."""
        self.all_statuses.clear()
        self.event_ids.clear()
        self.json_result = None
        self.error_types = {
            "credential_issues": False,
            "capacity_issues": False,
            "price_issues": False,
            "config_issues": False,
            "network_issues": False,
        }
        

display_state = DisplayState()


class RichConsoleHandler(logging.Handler):
    """
    Custom logging handler that shows log messages in the Rich UI.
    
    This handler streams log content to the console panel in the Rich UI.
    """
    
    def __init__(self, live: Live, layout: Layout, level: int = logging.INFO):
        """
        Initialize the handler.
        
        Args:
            live: Rich Live instance
            layout: Layout containing the console panel
            level: Logging level
        """
        super().__init__(level=level)
        self.live = live
        self.layout = layout
        self.messages: List[str] = ["Logs will appear here..."]
        
        # Use a formatter that matches our needs
        self.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        
        # Initialize the console panel right away
        self._update_console_panel()
    
    def _update_console_panel(self) -> None:
        """Update the console panel with current messages."""
        if self.layout is None or not hasattr(self.layout, "children"):
            return
            
        # Find the console panel (assumed to be the last child)
        if len(self.layout.children) < 3:
            return
            
        console_panel = self.layout.children[2].renderable
        if hasattr(console_panel, "renderable"):
            console_panel.renderable = "\n".join(self.messages)
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Process a log record.
        
        Args:
            record: Log record to process
        """
        try:
            # Don't output to console directly when Rich Live is active
            # Just store in the messages list for display in the UI
            
            # Format the message
            msg = self.format(record)
            
            # Clear the default message if it's still there
            if (
                len(self.messages) == 1
                and self.messages[0] == "Logs will appear here..."
            ):
                self.messages = []
            
            # Add the new message
            self.messages.append(msg)
            
            # Keep only the last 20 messages
            if len(self.messages) > 20:
                self.messages = self.messages[-20:]
            
            # Update the console panel
            self._update_console_panel()
            
        except Exception:
            self.handleError(record)


def make_progress_table() -> Table:
    """
    Create a table for instance status display.
    
    Returns:
        Rich Table object
    """
    # Get terminal width
    width = console.width
    
    # Calculate column widths based on available space
    id_width = 6
    region_width = min(15, max(10, int(width * 0.10)))
    zone_width = min(15, max(10, int(width * 0.10)))
    status_width = min(30, max(20, int(width * 0.20)))
    elapsed_width = 8
    instance_id_width = min(20, max(10, int(width * 0.12)))
    ip_width = min(15, max(10, int(width * 0.08)))
    
    # Create table with adaptive column widths
    table = Table(show_header=True, header_style="bold magenta", expand=False)
    
    # Add columns with appropriate widths
    table.add_column("ID", width=id_width, style="cyan", no_wrap=True)
    table.add_column("Region", width=region_width, style="cyan", no_wrap=True)
    table.add_column("Zone", width=zone_width, style="cyan", no_wrap=True)
    table.add_column("Status", width=status_width, style="yellow", no_wrap=True)
    table.add_column(
        "Time", width=elapsed_width, justify="right", style="magenta", no_wrap=True
    )
    table.add_column("Instance ID", width=instance_id_width, style="blue", no_wrap=True)
    table.add_column("Public IP", width=ip_width, style="green", no_wrap=True)
    table.add_column("Private IP", width=ip_width, style="blue", no_wrap=True)
    
    # Update elapsed time for all statuses
    for status in display_state.all_statuses.values():
        status.update_elapsed_time()
    
    # Sort statuses for consistent display
    sorted_statuses = sorted(
        display_state.all_statuses.values(), key=lambda x: (x.region, x.zone)
    )
    
    # Add rows to the table
    for status in sorted_statuses:
        table.add_row(
            status.id,
            status.region,
            status.zone,
            status.combined_status(),
            format_elapsed_time(status.elapsed_time),
            status.instance_id or "",
            status.public_ip or "",
            status.private_ip or "",
        )
    
    return table


def create_layout(progress: Progress, table: Table) -> Layout:
    """
    Create a responsive layout that adapts to terminal size.
    
    Args:
        progress: Progress bar widget
        table: Status table widget
        
    Returns:
        Layout object
    """
    layout = Layout()
    
    # Calculate panel heights based on terminal height
    height = console.height
    progress_height = min(4, max(3, int(height * 0.1)))  # 10% for progress
    console_height = min(6, max(4, int(height * 0.2)))  # 20% for console
    
    # Create progress panel
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )
    
    # Create console panel for log messages
    console_panel = Panel(
        "",  # Start with empty content
        title="Console Output",
        border_style="blue",
        padding=(0, 1),
    )
    
    # Split layout with responsive sizing
    layout.split(
        Layout(progress_panel, size=progress_height),
        Layout(table),  # This will take the remaining space (about 70%)
        Layout(console_panel, size=console_height),
    )
    
    return layout


def format_elapsed_time(seconds: float) -> str:
    """
    Format elapsed time in a human-readable format.
    
    Args:
        seconds: Elapsed time in seconds
        
    Returns:
        Formatted time string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def print_error(message: str, error_type: Optional[ErrorType] = None) -> None:
    """
    Print an error message to the console.
    
    Args:
        message: Error message
        error_type: Type of error
    """
    console.print(f"[bold red]ERROR:[/bold red] {message}")
    
    # Set error type in global state if provided
    if error_type:
        if error_type == ErrorType.CREDENTIAL_ISSUES:
            display_state.error_types["credential_issues"] = True
        elif error_type == ErrorType.CAPACITY_ISSUES:
            display_state.error_types["capacity_issues"] = True
        elif error_type == ErrorType.PRICE_ISSUES:
            display_state.error_types["price_issues"] = True
        elif error_type == ErrorType.CONFIG_ISSUES:
            display_state.error_types["config_issues"] = True
        elif error_type == ErrorType.NETWORK_ISSUES:
            display_state.error_types["network_issues"] = True


def print_warning(message: str) -> None:
    """
    Print a warning message to the console.
    
    Args:
        message: Warning message
    """
    console.print(f"[bold yellow]WARNING:[/bold yellow] {message}")


def print_success(message: str) -> None:
    """
    Print a success message to the console.
    
    Args:
        message: Success message
    """
    console.print(f"[bold green]SUCCESS:[/bold green] {message}")


def print_info(message: str) -> None:
    """
    Print an info message to the console.
    
    Args:
        message: Info message
    """
    console.print(message)


async def update_display(live: Live) -> None:
    """
    Update the live display with current status information.
    
    Args:
        live: Rich Live instance
    """
    try:
        # Create progress bar
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed} of {task.total}"),
            expand=True,
        )
        
        # Add the task
        task = progress.add_task(display_state.task_name, total=display_state.task_total)
        
        # Create initial layout
        table = make_progress_table()
        layout = create_layout(progress, table)
        
        # Store the layout in the display state
        display_state.layout = layout
        
        # Update the console handler if it exists
        rich_handler = None
        for handler in logger.handlers:
            if isinstance(handler, RichConsoleHandler):
                rich_handler = handler
                break
        
        if rich_handler is None:
            # Create a new handler if none exists
            rich_handler = RichConsoleHandler(live, layout)
            logger.addHandler(rich_handler)
        else:
            # Update the existing handler
            rich_handler.layout = layout
        
        # Update loop
        while not display_state.stop_event.is_set():
            # Update progress
            async with display_state.status_lock:
                display_state.event_ids.clear()
                progress.update(
                    task, 
                    completed=len(display_state.all_statuses),
                    refresh=True
                )
            
            # Update table and layout
            table = make_progress_table()
            layout = create_layout(progress, table)
            
            # Update the RichConsoleHandler with the new layout
            for handler in logger.handlers:
                if isinstance(handler, RichConsoleHandler):
                    handler.layout = layout
            
            # Update the display
            live.update(layout)
            
            # Wait before next update
            await asyncio.sleep(0.5)
    
    except Exception as e:
        logger.error(f"Error updating display: {str(e)}", exc_info=True)


async def start_display() -> None:
    """
    Start the display and update task.
    
    This function initializes the Rich Live display and starts the
    update task.
    """
    # Reset the display state
    display_state.reset()
    
    # Create initial progress and table
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    )
    table = make_progress_table()
    
    # Create layout
    layout = create_layout(progress, table)
    
    # Create and store the Live instance
    with Live(
        layout,
        console=console,
        refresh_per_second=5,
        auto_refresh=True,
        screen=True,
        transient=False,  # Keep the display visible after exit
    ) as live:
        # Store the live instance
        display_state.live = live
        
        # Add the rich console handler
        rich_handler = RichConsoleHandler(live, layout)
        logger.addHandler(rich_handler)
        
        # Start the display update task
        display_state.display_task = asyncio.create_task(update_display(live))
        
        try:
            # Wait for the stop event
            await display_state.stop_event.wait()
            
            # Keep the display open briefly
            await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            # Normal cancellation, ignore
            pass
        finally:
            # Remove the rich console handler
            logger.removeHandler(rich_handler)
            
            # Cancel the display task if it's still running
            if display_state.display_task and not display_state.display_task.done():
                display_state.display_task.cancel()
                try:
                    await display_state.display_task
                except asyncio.CancelledError:
                    pass


def stop_display() -> None:
    """Stop the display update task."""
    display_state.stop_event.set()


def setup_logging(
    verbose: bool = False, log_file: str = "debug.log", log_to_console: bool = True
) -> None:
    """
    Set up logging with a unified stream approach.
    
    Args:
        verbose: Enable verbose logging
        log_file: Path to log file
        log_to_console: Enable logging to console
    """
    # Set up root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set log level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO
    root_logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # Create file handler
    if log_file:
        # Truncate the log file
        try:
            with open(log_file, "w") as f:
                pass
        except Exception as e:
            print(f"Warning: Could not truncate log file {log_file}: {e}")
        
        # Create and configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Create console handler if requested, but don't output to stdout
    # during Rich Live display - instead the RichConsoleHandler will 
    # collect messages and show them in the UI
    if log_to_console:
        # Log messages will still be collected but not directly output
        # to console when Rich Live display is active
        pass
    
    # Log initial message (will be captured and displayed in UI)
    logger.info(f"Logging initialized at level {logging.getLevelName(log_level)}")
    if log_file:
        logger.info(f"Logging to {log_file}")


def create_error_table(error_types: Dict[str, bool]) -> Table:
    """
    Create a table for error diagnosis.
    
    Args:
        error_types: Dictionary tracking error types
        
    Returns:
        Rich Table object
    """
    # Create table
    table = Table(
        title="Error Diagnosis",
        show_header=True,
        header_style="bold red",
        box=box.ROUNDED,
    )
    
    # Add columns
    table.add_column("Error Type", style="yellow")
    table.add_column("Description", style="red")
    table.add_column("Solution", style="green")
    
    # Add rows based on error types
    if error_types["credential_issues"]:
        table.add_row(
            "Credential Issues",
            "AWS credentials are expired or invalid",
            "Run 'aws sso login' to refresh your credentials"
        )
    elif error_types["capacity_issues"]:
        table.add_row(
            "Capacity Issues",
            "AWS doesn't have capacity for the requested instance types",
            "Try different instance types or regions with more available capacity"
        )
    elif error_types["price_issues"]:
        table.add_row(
            "Price Issues",
            "Spot price is higher than the bid price",
            "Try different instance types with lower spot prices"
        )
    elif error_types["config_issues"]:
        table.add_row(
            "Configuration Issues",
            "Configuration contains invalid or incompatible settings",
            "Check instance types, AMI IDs, and region settings"
        )
    elif error_types["network_issues"]:
        table.add_row(
            "Network Issues",
            "Network connectivity or configuration problems",
            "Check VPC settings and security groups"
        )
    else:
        table.add_row(
            "Unknown Issues",
            "Could not determine the specific cause",
            "Check AWS console and logs for more details"
        )
    
    return table


def print_no_instances_created_error() -> None:
    """
    Print a comprehensive error when no instances were created.
    """
    console.print("\n[bold red]══════════════ CREATION FAILURE SUMMARY ══════════════[/bold red]")
    console.print("[bold red]NO INSTANCES WERE SUCCESSFULLY CREATED[/bold red]")
    
    # Create and display error table
    error_table = create_error_table(display_state.error_types)
    console.print(error_table)
    
    # Add troubleshooting steps
    console.print("\n[bold]Troubleshooting Steps:[/bold]")
    
    if display_state.error_types["capacity_issues"]:
        console.print("[green]1. Try using m6g.medium instead of t4g.small (recommended)[/green]")
        console.print("[green]2. Try regions with more capacity: us-east-1, us-east-2, us-west-2[/green]")
    elif display_state.error_types["price_issues"]:
        console.print("[green]1. Try using t3a.medium for better pricing[/green]")
        console.print("[green]2. Check current spot pricing in AWS console[/green]")
    elif display_state.error_types["config_issues"]:
        console.print("[green]1. Verify config.yaml AMI IDs and instance types[/green]")
        console.print("[green]2. Check that all regions are properly configured[/green]")
    else:
        console.print("[green]1. Check debug.log for detailed error messages[/green]")
        console.print("[green]2. Verify your AWS credentials and permissions[/green]")
        console.print("[green]3. Try running with --verbose flag for more details[/green]")