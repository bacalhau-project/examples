#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Quick validation wrapper - run this before committing or uploading.
Usage:
    ./validate.py         # Run all checks
    ./validate.py fix     # Auto-fix issues
    ./validate.py format  # Format code
"""

import subprocess
import sys

def main():
    """Run validation."""
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    
    cmd = ["uv", "run", "-s", "scripts/validate-all.py", action]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()