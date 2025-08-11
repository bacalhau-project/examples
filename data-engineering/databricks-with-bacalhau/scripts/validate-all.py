#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Comprehensive validation for all Python files in the project.
Run this before committing or uploading to Databricks.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def validate_notebooks() -> bool:
    """Run notebook-specific validation."""
    print("🔍 Validating Databricks notebooks...")
    
    # Run our custom validators
    scripts = [
        "scripts/validate-notebooks.py",
        "scripts/check-databricks-notebooks.py",
        "scripts/check-naming-consistency.py"
    ]
    
    all_passed = True
    for script in scripts:
        if Path(script).exists():
            exit_code, stdout, stderr = run_command(["uv", "run", "-s", script])
            if stdout:
                print(stdout)
            if exit_code != 0:
                all_passed = False
                if stderr:
                    print(f"❌ Error: {stderr}", file=sys.stderr)
    
    return all_passed


def run_ruff_check() -> bool:
    """Run ruff linter on all Python files."""
    print("\n🔍 Running ruff linter...")
    
    # Check if ruff is available
    exit_code, _, _ = run_command(["uv", "tool", "list"])
    if "ruff" not in _.lower() and exit_code == 0:
        print("Installing ruff...")
        run_command(["uv", "tool", "install", "ruff"])
    
    # Run ruff on different directories
    all_passed = True
    dirs_to_check = [
        ("databricks-uploader/*.py", None),
        ("scripts/*.py", None),
        ("databricks-notebooks/*.py", "databricks-notebooks/.ruff.toml"),
    ]
    
    for pattern, config in dirs_to_check:
        cmd = ["uv", "tool", "run", "ruff", "check", pattern]
        if config and Path(config).exists():
            cmd.extend(["--config", config])
        
        exit_code, stdout, stderr = run_command(cmd)
        if stdout:
            print(stdout)
        if exit_code != 0:
            all_passed = False
            print(f"❌ Ruff found issues in {pattern}")
            if stderr:
                print(stderr)
    
    return all_passed


def run_ruff_fix() -> bool:
    """Auto-fix issues with ruff."""
    print("\n🔧 Auto-fixing issues with ruff...")
    
    dirs_to_fix = [
        ("databricks-uploader/*.py", None),
        ("scripts/*.py", None),
        ("databricks-notebooks/*.py", "databricks-notebooks/.ruff.toml"),
    ]
    
    for pattern, config in dirs_to_fix:
        cmd = ["uv", "tool", "run", "ruff", "check", "--fix", pattern]
        if config and Path(config).exists():
            cmd.extend(["--config", config])
        
        exit_code, stdout, stderr = run_command(cmd)
        if stdout:
            print(f"Fixed issues in {pattern}:")
            print(stdout)
    
    return True


def format_code() -> bool:
    """Format code with black."""
    print("\n🎨 Formatting code with black...")
    
    # Check if black is available
    exit_code, _, _ = run_command(["uv", "tool", "list"])
    if "black" not in _.lower() and exit_code == 0:
        print("Installing black...")
        run_command(["uv", "tool", "install", "black"])
    
    # Format non-notebook files only
    dirs_to_format = [
        "databricks-uploader/*.py",
        "scripts/*.py",
    ]
    
    for pattern in dirs_to_format:
        cmd = ["uv", "tool", "run", "black", "--line-length", "100", pattern]
        exit_code, stdout, stderr = run_command(cmd)
        if stdout:
            print(stdout)
    
    print("Note: Skipping notebooks to preserve Databricks formatting")
    return True


def main():
    """Run validation based on command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Python code")
    parser.add_argument(
        "action",
        choices=["check", "fix", "format", "all"],
        default="check",
        nargs="?",
        help="Action to perform (default: check)"
    )
    
    args = parser.parse_args()
    
    if args.action == "fix":
        run_ruff_fix()
        print("\n✅ Auto-fix complete. Run 'check' to see remaining issues.")
        
    elif args.action == "format":
        format_code()
        print("\n✅ Formatting complete.")
        
    elif args.action == "all":
        # Run everything
        print("Running all validations and fixes...\n")
        run_ruff_fix()
        format_code()
        
        notebooks_ok = validate_notebooks()
        ruff_ok = run_ruff_check()
        
        if notebooks_ok and ruff_ok:
            print("\n✅ All checks passed!")
            return 0
        else:
            print("\n❌ Some checks failed. Fix the issues above.")
            return 1
            
    else:  # check
        notebooks_ok = validate_notebooks()
        ruff_ok = run_ruff_check()
        
        if notebooks_ok and ruff_ok:
            print("\n✅ All checks passed!")
            return 0
        else:
            print("\n❌ Validation failed. Run with 'fix' to auto-fix some issues:")
            print("  uv run -s scripts/validate-all.py fix")
            return 1


if __name__ == "__main__":
    sys.exit(main())