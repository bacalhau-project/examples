"""
Command-line interface parser for the Sensor Manager.
"""

import argparse
import os
import sys

# Try to get version from main module if available, otherwise use a default
try:
    # Check if main already defined version
    from sensor_manager.main import __version__
except (ImportError, ModuleNotFoundError):
    try:
        from sensor_manager import __version__
    except (ImportError, ModuleNotFoundError):
        # Fallback version
        __version__ = "0.1.0"

# Import command implementations
try:
    from sensor_manager.cli.commands.compose import compose_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.compose import compose_command
    except (ImportError, ModuleNotFoundError):
        compose_command = None

try:
    from sensor_manager.cli.commands.start import start_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.start import start_command
    except (ImportError, ModuleNotFoundError):
        start_command = None

try:
    from sensor_manager.cli.commands.stop import stop_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.stop import stop_command
    except (ImportError, ModuleNotFoundError):
        stop_command = None

try:
    from sensor_manager.cli.commands.cleanup import cleanup_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.cleanup import cleanup_command
    except (ImportError, ModuleNotFoundError):
        cleanup_command = None

try:
    from sensor_manager.cli.commands.monitor import monitor_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.monitor import monitor_command
    except (ImportError, ModuleNotFoundError):
        monitor_command = None

try:
    from sensor_manager.cli.commands.build import build_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.build import build_command
    except (ImportError, ModuleNotFoundError):
        build_command = None

try:
    from sensor_manager.cli.commands.query import query_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.query import query_command
    except (ImportError, ModuleNotFoundError):
        query_command = None

try:
    from sensor_manager.cli.commands.diagnostics import diagnostics_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.diagnostics import diagnostics_command
    except (ImportError, ModuleNotFoundError):
        diagnostics_command = None

try:
    from sensor_manager.cli.commands.logs import logs_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.logs import logs_command
    except (ImportError, ModuleNotFoundError):
        logs_command = None

try:
    from sensor_manager.cli.commands.clean import clean_command
except (ImportError, ModuleNotFoundError):
    try:
        from cli.commands.clean import clean_command
    except (ImportError, ModuleNotFoundError):
        clean_command = None


def create_parser():
    """Create and return the argument parser for the Sensor Manager CLI."""

    # Create the top-level parser
    parser = argparse.ArgumentParser(
        description="Sensor Manager - Manage all aspects of sensor simulation and Cosmos DB integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        title="commands", dest="command", help="Command to execute"
    )

    # "compose" command
    compose_parser = subparsers.add_parser(
        "compose", help="Generate Docker Compose file for sensor simulation"
    )
    compose_parser.add_argument(
        "--output",
        type=str,
        default="docker-compose.yml",
        help="Path to output Docker Compose file",
    )
    compose_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file with city information",
    )
    compose_parser.add_argument(
        "--sensors-per-city", type=int, default=5, help="Number of sensors per city"
    )
    compose_parser.add_argument(
        "--readings-per-second",
        type=int,
        default=1,
        help="Number of readings per second",
    )
    compose_parser.add_argument(
        "--anomaly-probability",
        type=float,
        default=0.05,
        help="Probability of anomalies",
    )
    compose_parser.add_argument(
        "--upload-interval",
        type=int,
        default=30,
        help="Interval for uploader in seconds",
    )
    compose_parser.add_argument(
        "--archive-format", type=str, default="Parquet", help="Format for archived data"
    )
    compose_parser.add_argument(
        "--sensor-config",
        type=str,
        default="config/sensor-config.yaml",
        help="Path to sensor configuration file",
    )
    compose_parser.add_argument(
        "--compose-config",
        type=str,
        default="config.yaml",
        help="Path to config file for uploader container",
    )
    compose_parser.add_argument(
        "--uploader-tag",
        type=str,
        help="Tag for the CosmosUploader image to use (NEVER use 'latest')",
    )
    if compose_command:
        compose_parser.set_defaults(func=compose_command)

    # "start" command
    start_parser = subparsers.add_parser(
        "start", help="Start sensor simulation with configuration"
    )
    start_parser.add_argument(
        "--no-rebuild", action="store_true", help="Skip rebuilding the uploader image"
    )
    start_parser.add_argument(
        "--project-name",
        type=str,
        help="Specify a custom project name for Docker Compose",
    )
    start_parser.add_argument(
        "--no-diagnostics",
        action="store_true",
        help="Skip running diagnostics after startup",
    )
    start_parser.add_argument(
        "--sensor-config",
        type=str,
        default="config/sensor-config.yaml",
        help="Path to sensor configuration file",
    )
    start_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file with city information",
    )
    start_parser.add_argument(
        "--max-cities", type=int, default=5, help="Maximum number of cities to use"
    )
    start_parser.add_argument(
        "--sensors-per-city", type=int, default=5, help="Number of sensors per city"
    )
    start_parser.add_argument(
        "--readings-per-second",
        type=int,
        default=1,
        help="Number of readings per second",
    )
    start_parser.add_argument(
        "--anomaly-probability",
        type=float,
        default=0.05,
        help="Probability of anomalies",
    )
    start_parser.add_argument(
        "--upload-interval",
        type=int,
        default=30,
        help="Interval for uploader in seconds",
    )
    start_parser.add_argument(
        "--archive-format", type=str, default="Parquet", help="Format for archived data"
    )
    start_parser.add_argument(
        "--compose-config",
        type=str,
        default="config.yaml",
        help="Path to config file for uploader container",
    )
    start_parser.add_argument(
        "--tag", type=str, help="Tag for the uploader image (when building locally)"
    )
    start_parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Don't tag the uploader image (when building locally)",
    )
    start_parser.add_argument(
        "--uploader-tag",
        type=str,
        help="Tag for the CosmosUploader image to use (NEVER use 'latest')",
    )
    if start_command:
        start_parser.set_defaults(func=start_command)

    # "stop" command
    stop_parser = subparsers.add_parser("stop", help="Stop all running containers")
    stop_parser.add_argument(
        "--no-prompt", action="store_true", help="Skip confirmation prompts"
    )
    if stop_command:
        stop_parser.set_defaults(func=stop_command)

    # "monitor" command
    monitor_parser = subparsers.add_parser(
        "monitor", help="Monitor sensor status and data uploads"
    )
    monitor_parser.add_argument(
        "--plain", action="store_true", help="Disable colored output"
    )
    if monitor_command:
        monitor_parser.set_defaults(func=monitor_command)

    # "cleanup" command
    cleanup_parser = subparsers.add_parser(
        "cleanup", help="Force cleanup all containers"
    )
    if cleanup_command:
        cleanup_parser.set_defaults(func=cleanup_command)

    # "build" command
    build_parser = subparsers.add_parser("build", help="Build the CosmosUploader image")
    build_parser.add_argument(
        "--tag",
        type=str,
        help="Tag for the uploader image (default: auto-generated timestamp)",
    )
    build_parser.add_argument(
        "--no-tag", action="store_true", help="Don't tag the uploader image"
    )
    if build_command:
        build_parser.set_defaults(func=build_command)

    # "query" command
    query_parser = subparsers.add_parser(
        "query", help="Query SQLite databases for sensor readings"
    )
    query_group = query_parser.add_mutually_exclusive_group()
    query_group.add_argument(
        "--all",
        action="store_true",
        help="Query all databases found in the data directory",
    )
    query_group.add_argument(
        "--list", action="store_true", help="List all sensors found in the databases"
    )
    query_group.add_argument(
        "--sensor-id", type=str, help="Query specific sensor by ID"
    )
    if query_command:
        query_parser.set_defaults(func=query_command)

    # "diagnostics" command
    diagnostics_parser = subparsers.add_parser(
        "diagnostics",
        help="Run system diagnostics to check health of sensors and uploaders",
    )
    if diagnostics_command:
        diagnostics_parser.set_defaults(func=diagnostics_command)

    # "logs" command
    logs_parser = subparsers.add_parser(
        "logs", help="View logs from running containers"
    )
    logs_parser.add_argument(
        "--no-follow", action="store_true", help="Don't follow log output"
    )
    logs_parser.add_argument(
        "services",
        nargs="*",
        help="Service names to show logs for (leave empty for all services)",
    )
    if logs_command:
        logs_parser.set_defaults(func=logs_command)

    # "clean" command
    clean_parser = subparsers.add_parser("clean", help="Delete all data from Cosmos DB")
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    clean_parser.add_argument(
        "--yes", action="store_true", help="Skip confirmation prompts"
    )
    clean_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file with Cosmos DB settings",
    )
    if clean_command:
        clean_parser.set_defaults(func=clean_command)

    return parser
