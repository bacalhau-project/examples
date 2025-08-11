#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Check for consistent naming across the codebase.
Ensures we use sensor_readings, not sensor_data.
"""

import re
import sys
from pathlib import Path


def check_file_for_wrong_names(file_path: Path) -> list[str]:
    """Check a file for incorrect naming patterns."""
    issues = []
    
    # Skip binary files and specific directories
    skip_dirs = {'.git', '__pycache__', '.ruff_cache', 'node_modules', '.specstory', 'archive', '.claude'}
    if any(part in skip_dirs for part in file_path.parts):
        return issues
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except (UnicodeDecodeError, PermissionError):
        return issues  # Skip binary or inaccessible files
    
    # Patterns to check
    wrong_patterns = [
        # Wrong table names in SQL
        (r'\bFROM\s+sensor_data\b', 'Table should be sensor_readings, not sensor_data'),
        (r'\bINTO\s+sensor_data\b', 'Table should be sensor_readings, not sensor_data'),
        (r'\bTABLE\s+sensor_data\b', 'Table should be sensor_readings, not sensor_data'),
        (r'\bUPDATE\s+sensor_data\b', 'Table should be sensor_readings, not sensor_data'),
        
        # Wrong schema/database names
        (r'DATABRICKS_DATABASE\s*=\s*["\']?sensor_data', 'Schema should be sensor_readings'),
        (r'DATABRICKS_SCHEMA\s*=\s*["\']?sensor_data', 'Schema should be sensor_readings'),
        (r'\.sensor_data\.', 'Schema reference should be .sensor_readings.'),
        
        # Wrong table prefixes in Databricks
        (r'sensor_data_ingestion', 'Should be sensor_readings_ingestion'),
        (r'sensor_data_validated', 'Should be sensor_readings_validated'),
        (r'sensor_data_enriched', 'Should be sensor_readings_enriched'),
        (r'sensor_data_aggregated', 'Should be sensor_readings_aggregated'),
        (r'sensor_data_raw', 'Should be sensor_readings_raw'),
        (r'sensor_data_filtered', 'Should be sensor_readings_filtered'),
        (r'sensor_data_emergency', 'Should be sensor_readings_emergency'),
        (r'sensor_data_schematized', 'Should be sensor_readings_schematized'),
    ]
    
    # Exceptions - these are okay
    exceptions = [
        'sensor_data.db',  # SQLite database file name is okay
        'sensor_data_schema.json',  # Schema file name is okay
        '_read_sensor_data',  # Method names are okay
        'create_test_sensor_data',  # Script references are okay
        '# Wrong schema name',  # Comments explaining the issue
        '# Old wrong names',  # Comments about old names
        'NEVER use sensor_data',  # Documentation about not using it
    ]
    
    for i, line in enumerate(lines, 1):
        # Skip if line contains an exception
        if any(exc in line for exc in exceptions):
            continue
            
        # Skip comments and documentation
        if line.strip().startswith('#') or line.strip().startswith('//'):
            continue
        
        for pattern, message in wrong_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(f"{file_path}:{i}: {message}")
                issues.append(f"  Line: {line.strip()}")
    
    return issues


def main():
    """Check all files for naming consistency."""
    print("🔍 Checking for naming consistency (sensor_readings vs sensor_data)...\n")
    
    # Directories to check
    check_dirs = [
        'databricks-uploader',
        'databricks-notebooks', 
        'scripts',
        'tests',
        'pipeline-manager',
        'sample-sensor',
        'docs',
    ]
    
    # File extensions to check
    extensions = {'.py', '.yaml', '.yml', '.sql', '.sh', '.md', '.json'}
    
    all_issues = []
    files_checked = 0
    
    for dir_name in check_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
            
        for file_path in dir_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in extensions:
                files_checked += 1
                issues = check_file_for_wrong_names(file_path)
                all_issues.extend(issues)
    
    # Also check root level files
    for file_path in Path('.').glob('*'):
        if file_path.is_file() and file_path.suffix in extensions:
            files_checked += 1
            issues = check_file_for_wrong_names(file_path)
            all_issues.extend(issues)
    
    print(f"Checked {files_checked} files\n")
    
    if all_issues:
        print("❌ Found naming inconsistencies:\n")
        for issue in all_issues:
            print(f"  {issue}")
        
        print(f"\n❌ Total issues: {len([i for i in all_issues if not i.startswith('  Line:')])}")
        print("\nFix these issues to ensure consistent naming:")
        print("  - Use 'sensor_readings' for table and schema names")
        print("  - Use 'sensor_readings_' prefix for Databricks tables")
        print("  - Never use 'sensor_data' except for the SQLite file name")
        return 1
    else:
        print("✅ All files use consistent naming!")
        print("  - SQLite table: sensor_readings")
        print("  - Databricks schema: sensor_readings")
        print("  - Databricks tables: sensor_readings_*")
        return 0


if __name__ == "__main__":
    sys.exit(main())