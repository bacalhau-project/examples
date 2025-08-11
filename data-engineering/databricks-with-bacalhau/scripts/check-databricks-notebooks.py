#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Pre-commit hook to check Databricks notebooks for common issues.
Prevents deployment of notebooks with unsupported triggers on serverless compute.
"""

import re
import sys
from pathlib import Path


def check_notebook_for_issues(file_path: Path) -> list[str]:
    """Check a Databricks notebook for common issues."""
    issues = []
    
    with open(file_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Check for processingTime trigger
    processing_time_pattern = r'\.trigger\s*\(\s*processingTime\s*='
    continuous_pattern = r'\.trigger\s*\(\s*continuous\s*='
    
    for i, line in enumerate(lines, 1):
        if re.search(processing_time_pattern, line):
            issues.append(
                f"{file_path}:{i}: ERROR: processingTime trigger not supported "
                "on serverless compute. Use availableNow=True or once=True instead."
            )
        
        if re.search(continuous_pattern, line):
            issues.append(
                f"{file_path}:{i}: ERROR: continuous trigger not supported "
                "on serverless compute. Use availableNow=True or once=True instead."
            )
    
    # Check for old path patterns (if migrated to flat structure)
    old_path_patterns = [
        r'/raw/\d{4}/\d{2}/\d{2}/',  # Old nested date structure
        r'/ingestion/\d{4}/\d{2}/\d{2}/',
        r'recursiveFileLookup.*true',  # Not needed for flat structure
    ]
    
    for pattern in old_path_patterns:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                issues.append(
                    f"{file_path}:{i}: WARNING: Found old nested path pattern. "
                    "Consider using flat file structure at bucket root."
                )
    
    # Check for missing checkpoint location in streaming queries
    writestream_pattern = r'\.writeStream'
    checkpoint_pattern = r'\.option\s*\(\s*["\']checkpointLocation["\']'
    
    if re.search(writestream_pattern, content):
        # Find all writeStream occurrences
        for i, line in enumerate(lines, 1):
            if '.writeStream' in line:
                # Check if checkpointLocation is specified within next 10 lines
                found_checkpoint = False
                for j in range(i, min(i + 10, len(lines))):
                    if 'checkpointLocation' in lines[j]:
                        found_checkpoint = True
                        break
                    if '.start()' in lines[j]:
                        break
                
                if not found_checkpoint:
                    issues.append(
                        f"{file_path}:{i}: ERROR: Streaming query without checkpoint location. "
                        "Databricks requires explicit checkpoint: .option('checkpointLocation', 'path')"
                    )
    
    # Check for missing error handling in streaming queries
    if '.writeStream' in content:
        if 'try:' not in content or 'except' not in content:
            issues.append(
                f"{file_path}: WARNING: Streaming query without error handling. "
                "Consider adding try/except blocks."
            )
    
    # Check for hardcoded bucket names without variables
    hardcoded_buckets = re.findall(
        r's3://expanso-databricks-[a-z]+-us-west-2/',
        content
    )
    if hardcoded_buckets and 'BUCKET =' not in content:
        issues.append(
            f"{file_path}: WARNING: Hardcoded S3 bucket names found. "
            "Consider using configuration variables."
        )
    
    # Check for query.exception without parentheses
    exception_pattern = r'query\.exception(?!\(\))[^(]'
    for i, line in enumerate(lines, 1):
        if re.search(exception_pattern, line):
            issues.append(
                f"{file_path}:{i}: ERROR: query.exception is a method, not a property. "
                "Use query.exception() with parentheses."
            )
    
    return issues


def main():
    """Check all Databricks notebooks for issues."""
    # Find all Python files in databricks-notebooks directory
    notebooks_dir = Path('databricks-notebooks')
    
    if not notebooks_dir.exists():
        print("No databricks-notebooks directory found.")
        return 0
    
    all_issues = []
    
    for notebook in notebooks_dir.glob('*.py'):
        issues = check_notebook_for_issues(notebook)
        all_issues.extend(issues)
    
    if all_issues:
        print("Databricks notebook validation failed:\n")
        for issue in all_issues:
            print(f"  {issue}")
        print(f"\nFound {len(all_issues)} issue(s) in Databricks notebooks.")
        print("\nFix these issues before committing:")
        print("  - Replace processingTime triggers with availableNow=True")
        print("  - Replace continuous triggers with once=True")
        print("  - Update paths for flat file structure if needed")
        print("  - Add error handling for streaming queries")
        return 1
    
    print("✅ All Databricks notebooks passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())