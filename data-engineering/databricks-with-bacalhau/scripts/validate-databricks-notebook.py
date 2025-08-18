#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Simple validator for Databricks notebooks.
Checks for common issues that would prevent notebooks from running in Databricks.
"""

import sys
import ast
from pathlib import Path


def validate_notebook(notebook_path: Path, quiet: bool = False) -> bool:
    """
    Validate a Databricks notebook for common issues.

    Returns True if valid, False otherwise.
    """
    if not notebook_path.exists():
        if not quiet:
            print(f"❌ File not found: {notebook_path}")
        return False

    content = notebook_path.read_text()

    # Check 1: Valid Python syntax
    try:
        ast.parse(content)
    except SyntaxError as e:
        if not quiet:
            print(f"❌ Syntax error in {notebook_path}: {e}")
        return False

    # Check 2: No unsupported triggers for serverless
    issues = []

    if ".trigger(processingTime" in content:
        issues.append("Uses processingTime trigger (not supported in serverless)")

    if ".trigger(continuous" in content:
        issues.append("Uses continuous trigger (not supported in serverless)")

    # Check 3: No imports of PySpark (it's pre-imported in Databricks)
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        # Skip MAGIC comments
        if line.strip().startswith("# MAGIC"):
            continue

        # Check for problematic imports
        if "from pyspark.sql import SparkSession" in line:
            issues.append(f"Line {i}: Imports SparkSession (already available in Databricks)")

        if "spark = SparkSession.builder" in line:
            issues.append(
                f"Line {i}: Creates SparkSession (already exists as 'spark' in Databricks)"
            )

    # Check 4: Has checkpoint location for writeStream operations
    if ".writeStream" in content and "checkpointLocation" not in content:
        issues.append("Has writeStream without checkpointLocation")

    # Report issues
    if issues:
        if not quiet:
            print(f"❌ Validation failed for {notebook_path}:")
            for issue in issues:
                print(f"   - {issue}")
        return False

    if not quiet:
        print(f"✅ {notebook_path} is valid")

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate-databricks-notebook.py <notebook_path> [--quiet]")
        sys.exit(1)

    notebook_path = Path(sys.argv[1])
    quiet = "--quiet" in sys.argv

    if validate_notebook(notebook_path, quiet):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
