#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-json-logger>=2.0.0",
#     "rich>=13.0.0"
# ]
# ///

"""
Comprehensive Logging System for Databricks Pipeline

Provides structured logging with:
- JSON formatting for machine parsing
- Rich console output for human readability
- Log rotation and archival
- Performance metrics tracking
- Error aggregation and alerting
"""

import json
import logging
import logging.handlers
import os
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table


class PipelineLogger:
    """Centralized logging configuration for the pipeline."""

    _instances = {}

    def __new__(cls, name: str, *args, **kwargs):
        """Singleton per logger name."""
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
        return cls._instances[name]

    def __init__(
        self,
        name: str,
        log_dir: str = "logs",
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        enable_json: bool = True,
        enable_console: bool = True,
        enable_metrics: bool = True,
    ):
        """Initialize the pipeline logger.

        Args:
            name: Logger name (usually module name)
            log_dir: Directory for log files
            console_level: Console logging level
            file_level: File logging level
            enable_json: Enable JSON formatted logs
            enable_console: Enable rich console output
            enable_metrics: Enable metrics collection
        """
        # Skip if already initialized
        if hasattr(self, "_initialized"):
            return

        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self.console_level = console_level
        self.file_level = file_level
        self.enable_json = enable_json
        self.enable_console = enable_console
        self.enable_metrics = enable_metrics

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers

        # Setup handlers
        self._setup_handlers()

        # Metrics tracking
        self.metrics = {"errors": 0, "warnings": 0, "records_processed": 0, "processing_time": 0.0}

        self._initialized = True

    def _setup_handlers(self):
        """Set up logging handlers."""
        # Console handler with Rich
        if self.enable_console:
            console_handler = RichHandler(
                console=Console(stderr=True),
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
            )
            console_handler.setLevel(getattr(logging, self.console_level))
            console_formatter = logging.Formatter("%(name)s - %(message)s")
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # JSON file handler with rotation
        if self.enable_json:
            json_file = self.log_dir / f"{self.name}.json"
            json_handler = logging.handlers.RotatingFileHandler(
                json_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            json_handler.setLevel(getattr(logging, self.file_level))

            # Custom JSON formatter
            json_formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
            json_handler.setFormatter(json_formatter)
            self.logger.addHandler(json_handler)

        # Error file handler
        error_file = self.log_dir / f"{self.name}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s"
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)

        # Performance metrics handler (daily rotation)
        if self.enable_metrics:
            metrics_file = self.log_dir / f"{self.name}_metrics.log"
            metrics_handler = logging.handlers.TimedRotatingFileHandler(
                metrics_file, when="midnight", interval=1, backupCount=30
            )
            metrics_handler.setLevel(logging.INFO)
            metrics_formatter = logging.Formatter("%(asctime)s - %(message)s")
            metrics_handler.setFormatter(metrics_formatter)
            # Add filter to only log metrics
            metrics_handler.addFilter(MetricsFilter())
            self.logger.addHandler(metrics_handler)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.metrics["warnings"] += 1
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, exc_info: bool = True, **kwargs):
        """Log error message."""
        self.metrics["errors"] += 1
        self.logger.error(message, exc_info=exc_info, extra=kwargs)

    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """Log critical message."""
        self.metrics["errors"] += 1
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)

    def log_metric(
        self, metric_name: str, value: int | float, unit: str | None = None, **tags
    ):
        """Log a metric value.

        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Optional unit of measurement
            **tags: Additional tags for the metric
        """
        metric_data = {
            "metric_type": "metric",
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "tags": tags,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.logger.info(f"METRIC: {metric_name}={value}", extra=metric_data)

    def log_event(self, event_name: str, event_type: str = "info", **data):
        """Log a business event.

        Args:
            event_name: Name of the event
            event_type: Type of event (info, warning, error)
            **data: Event data
        """
        event_data = {
            "event_type": event_type,
            "event_name": event_name,
            "event_data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.logger.info(f"EVENT: {event_name}", extra=event_data)

    def log_performance(
        self, operation: str, duration: float, records: int | None = None, **metadata
    ):
        """Log performance metrics.

        Args:
            operation: Name of the operation
            duration: Duration in seconds
            records: Number of records processed
            **metadata: Additional metadata
        """
        self.metrics["processing_time"] += duration
        if records:
            self.metrics["records_processed"] += records

        perf_data = {
            "performance_type": "timing",
            "operation": operation,
            "duration_seconds": duration,
            "records": records,
            "records_per_second": records / duration if records and duration > 0 else None,
            "metadata": metadata,
        }
        self.logger.info(f"PERFORMANCE: {operation} took {duration:.2f}s", extra=perf_data)

    def log_exception(self, exception: Exception, context: dict[str, Any] | None = None):
        """Log an exception with full context.

        Args:
            exception: The exception to log
            context: Additional context information
        """
        exc_data = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "exception_traceback": traceback.format_exc(),
            "context": context or {},
        }
        self.error(f"Exception: {type(exception).__name__}: {exception}", exc_info=True, **exc_data)

    def get_summary(self) -> dict[str, Any]:
        """Get logging summary statistics."""
        return {
            "logger_name": self.name,
            "metrics": self.metrics.copy(),
            "log_directory": str(self.log_dir),
            "levels": {"console": self.console_level, "file": self.file_level},
        }

    def print_summary(self):
        """Print a rich summary table."""
        console = Console()

        table = Table(title=f"Logger Summary: {self.name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Errors", str(self.metrics["errors"]))
        table.add_row("Warnings", str(self.metrics["warnings"]))
        table.add_row("Records Processed", f"{self.metrics['records_processed']:,}")
        table.add_row("Processing Time", f"{self.metrics['processing_time']:.2f}s")
        table.add_row("Log Directory", str(self.log_dir))

        console.print(table)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = datetime.now(UTC).isoformat()

        # Add level name
        log_record["level"] = record.levelname

        # Add caller information
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add process/thread info
        log_record["process"] = record.process
        log_record["thread"] = record.thread

        # Add hostname
        log_record["hostname"] = os.environ.get("HOSTNAME", "unknown")

        # Add Bacalhau context if available
        if os.environ.get("BACALHAU_JOB_ID"):
            log_record["bacalhau_job_id"] = os.environ.get("BACALHAU_JOB_ID")
            log_record["bacalhau_node_id"] = os.environ.get("BACALHAU_NODE_ID")


class MetricsFilter(logging.Filter):
    """Filter to only allow metrics logs."""

    def filter(self, record):
        """Filter log records."""
        return hasattr(record, "metric_type") or hasattr(record, "performance_type")


class LogAggregator:
    """Aggregates logs for analysis and alerting."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize the log aggregator."""
        self.log_dir = Path(log_dir)
        self.console = Console()

    def analyze_errors(self, hours: int = 24) -> dict[str, Any]:
        """Analyze error patterns in recent logs.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with error analysis
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        errors = []

        # Read error log files
        for error_file in self.log_dir.glob("*_errors.log"):
            with open(error_file) as f:
                for line in f:
                    try:
                        # Parse timestamp from log line
                        timestamp_str = line.split(" - ")[0]
                        timestamp = datetime.fromisoformat(timestamp_str.replace(" ", "T"))

                        if timestamp > cutoff_time:
                            errors.append(
                                {
                                    "timestamp": timestamp,
                                    "message": line.strip(),
                                    "source": error_file.stem,
                                }
                            )
                    except:
                        continue

        # Analyze patterns
        error_types = {}
        for error in errors:
            # Extract error type from message
            if "Exception:" in error["message"]:
                error_type = error["message"].split("Exception:")[0].split()[-1]
                error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total_errors": len(errors),
            "error_types": error_types,
            "time_range": f"Last {hours} hours",
            "sources": list(set(e["source"] for e in errors)),
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get aggregated performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        metrics = {}

        # Read metrics log files
        for metrics_file in self.log_dir.glob("*_metrics.log"):
            with open(metrics_file) as f:
                for line in f:
                    try:
                        if "METRIC:" in line:
                            # Parse metric from log line
                            metric_part = line.split("METRIC:")[1].strip()
                            if "=" in metric_part:
                                name, value = metric_part.split("=", 1)
                                metrics[name] = float(value.split()[0])
                    except:
                        continue

        return metrics

    def print_analysis(self):
        """Print log analysis summary."""
        # Error analysis
        error_analysis = self.analyze_errors()

        error_panel = Panel(
            f"Total Errors: {error_analysis['total_errors']}\n"
            + f"Time Range: {error_analysis['time_range']}\n"
            + f"Error Types: {json.dumps(error_analysis['error_types'], indent=2)}",
            title="Error Analysis",
            border_style="red",
        )
        self.console.print(error_panel)

        # Performance metrics
        perf_metrics = self.get_performance_metrics()

        if perf_metrics:
            metrics_table = Table(title="Performance Metrics")
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="green")

            for metric, value in perf_metrics.items():
                metrics_table.add_row(metric, f"{value:,.2f}")

            self.console.print(metrics_table)


# Convenience function for getting logger
def get_logger(name: str, **kwargs) -> PipelineLogger:
    """Get or create a pipeline logger.

    Args:
        name: Logger name
        **kwargs: Additional configuration

    Returns:
        PipelineLogger instance
    """
    return PipelineLogger(name, **kwargs)


def setup_pipeline_logging(
    log_level: str = "INFO", log_dir: str = "logs", enable_json: bool = True
):
    """Set up logging for the entire pipeline.

    Args:
        log_level: Default log level
        log_dir: Directory for log files
        enable_json: Enable JSON logging
    """
    # Create log directory
    Path(log_dir).mkdir(exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # Add rich handler to root
    console_handler = RichHandler(
        console=Console(stderr=True), show_time=True, rich_tracebacks=True
    )
    console_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)

    # Log startup
    logger = get_logger("pipeline")
    logger.info(
        "Pipeline logging initialized",
        log_level=log_level,
        log_dir=log_dir,
        enable_json=enable_json,
    )


def run_demo():
    """Run a demo of the logging system."""
    print("\n=== Pipeline Logging System Demo ===\n")

    # Setup logging
    setup_pipeline_logging(log_level="DEBUG")

    # Get logger
    logger = get_logger("demo_pipeline")

    # Log various messages
    logger.info("Starting pipeline demo")
    logger.debug("Debug information", component="data_loader", records=1000)

    # Log metrics
    logger.log_metric("temperature", 65.5, unit="celsius", sensor="CHI_001")
    logger.log_metric("records_processed", 1500)

    # Log events
    logger.log_event("pipeline_started", pipeline="hourly_aggregation")
    logger.log_event("anomaly_detected", event_type="warning", sensor="NYC_002", temperature=85.0)

    # Log performance
    import time

    start = time.time()
    time.sleep(0.1)  # Simulate work
    duration = time.time() - start
    logger.log_performance("data_transformation", duration, records=1000)

    # Log warning and error
    logger.warning("High temperature detected", temperature=78.0, sensor="LAX_003")

    try:
        1 / 0
    except Exception as e:
        logger.log_exception(e, context={"operation": "division", "values": [1, 0]})

    # Print summary
    print("\n" + "=" * 50 + "\n")
    logger.print_summary()

    # Analyze logs
    print("\n" + "=" * 50 + "\n")
    aggregator = LogAggregator()
    aggregator.print_analysis()


if __name__ == "__main__":
    run_demo()
