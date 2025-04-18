#!/usr/bin/env uv run -s
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
Entry point for the Sensor Manager CLI.
"""

import os
import sys

# Add the parent directory to path so we can import relatively
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Define version here to avoid circular imports
__version__ = "0.1.0"

# Now we can import the parser
from sensor_manager.cli.parser import create_parser


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if hasattr(args, "func"):
            # Call the command handler function
            result = args.func(args)
            return result if isinstance(result, int) else 0
        else:
            # No command specified, show help
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        from sensor_manager.utils import logging as log
        log.error(f"Error executing command: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
