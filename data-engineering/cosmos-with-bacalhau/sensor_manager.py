#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0.0",
#     "pyyaml>=6.0",
#     "jinja2>=3.0.0",
#     "rich>=10.0.0",
# ]
# ///
"""
Sensor Manager - Wrapper script for the Sensor Manager CLI.

This script provides a convenient way to run the Sensor Manager CLI.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to sys.path so we can import sensor_manager
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from sensor_manager.cli.parser import create_parser
except ImportError:
    print("Error: Could not import sensor_manager. Make sure it's installed.")
    sys.exit(1)


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        # Call the command handler function
        result = args.func(args)
        return result if result is not None else 0
    else:
        # No command specified, show help
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())