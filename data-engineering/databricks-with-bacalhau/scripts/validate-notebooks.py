#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Comprehensive validation for Databricks notebooks before upload.
Catches common errors that would fail in Databricks runtime.
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple


class NotebookValidator(ast.NodeVisitor):
    """AST visitor to find common Databricks notebook issues."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []
        self.current_line = 0
    
    def visit_Call(self, node):
        """Check method calls for common issues."""
        # Check for exception access without call
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'exception' and isinstance(node.func.value, ast.Name):
                # This is correct: query.exception()
                pass
            elif hasattr(node.func, 'value') and hasattr(node.func.value, 'id'):
                # Check for methods that should be called
                var_name = node.func.value.id if hasattr(node.func.value, 'id') else ''
                if 'query' in var_name.lower() and node.func.attr in ['stop', 'awaitTermination']:
                    # These are being called correctly
                    pass
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        """Check attribute access for methods used as properties."""
        if hasattr(node, 'value') and hasattr(node.value, 'id'):
            var_name = node.value.id if hasattr(node.value, 'id') else ''
            
            # Check for query.exception without parentheses
            if 'query' in var_name.lower() and node.attr == 'exception':
                # Check if this is being called (parent is Call)
                parent = getattr(node, 'parent', None)
                if not isinstance(parent, ast.Call):
                    self.issues.append(
                        f"Line {node.lineno}: query.exception should be called with parentheses: query.exception()"
                    )
        
        self.generic_visit(node)


def validate_notebook_syntax(file_path: Path) -> List[str]:
    """Validate Python syntax and common patterns."""
    issues = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Parse AST
        try:
            tree = ast.parse(content, filename=str(file_path))
            
            # Add parent references for better analysis
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    child.parent = parent
            
            # Run validator
            validator = NotebookValidator(str(file_path))
            validator.visit(tree)
            issues.extend(validator.issues)
            
        except SyntaxError as e:
            issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
            
    except Exception as e:
        issues.append(f"Error reading file: {e}")
    
    return issues


def validate_streaming_patterns(file_path: Path) -> List[str]:
    """Validate Databricks streaming specific patterns."""
    issues = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    in_writestream = False
    writestream_line = 0
    found_checkpoint = False
    found_trigger = False
    trigger_type = None
    
    for i, line in enumerate(lines, 1):
        # Track writeStream blocks
        if '.writeStream' in line:
            in_writestream = True
            writestream_line = i
            found_checkpoint = False
            found_trigger = False
            trigger_type = None
        
        # Check for checkpoint within writeStream block
        if in_writestream and 'checkpointLocation' in line:
            found_checkpoint = True
        
        # Check for trigger type
        if in_writestream and '.trigger(' in line:
            found_trigger = True
            if 'processingTime' in line:
                trigger_type = 'processingTime'
                issues.append(
                    f"Line {i}: processingTime trigger not supported on serverless. Use availableNow=True"
                )
            elif 'continuous' in line:
                trigger_type = 'continuous'
                issues.append(
                    f"Line {i}: continuous trigger not supported on serverless. Use availableNow=True or once=True"
                )
        
        # Check for .start() which ends the writeStream block
        if in_writestream and '.start()' in line:
            if not found_checkpoint:
                issues.append(
                    f"Line {writestream_line}: Streaming query missing checkpoint location. "
                    "Add .option('checkpointLocation', 'path')"
                )
            in_writestream = False
    
    return issues


def validate_imports(file_path: Path) -> List[str]:
    """Validate imports and dependencies."""
    issues = []
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Skip import checks if using star imports (common in Databricks)
    if 'from pyspark.sql.functions import *' in content:
        return issues
    
    # Check for common missing imports only if not using star imports
    patterns = [
        (r'\bcurrent_timestamp\(', 'from pyspark.sql.functions import current_timestamp'),
        (r'\bcol\(', 'from pyspark.sql.functions import col'),
        (r'StructType\(', 'from pyspark.sql.types import StructType'),
    ]
    
    for pattern, import_stmt in patterns:
        if re.search(pattern, content) and import_stmt not in content:
            issues.append(f"Missing import: {import_stmt}")
    
    return issues


def validate_databricks_specific(file_path: Path) -> List[str]:
    """Validate Databricks-specific requirements."""
    issues = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Check for common Databricks issues
    for i, line in enumerate(lines, 1):
        # Check for display() without checkpoint
        if 'display(' in line and 'checkpointLocation' not in line:
            # Check next few lines for checkpoint
            found_checkpoint = False
            for j in range(i, min(i + 3, len(lines))):
                if 'checkpointLocation' in lines[j]:
                    found_checkpoint = True
                    break
            if not found_checkpoint and '.writeStream' in ''.join(lines[max(0, i-5):i]):
                issues.append(
                    f"Line {i}: display() with streaming needs checkpointLocation parameter"
                )
        
        # Check for incorrect exception handling
        if re.search(r'except\s*:', line) or re.search(r'except\s+Exception\s*:', line):
            # Check if there's proper error handling (check next line)
            if i < len(lines) and 'pass' in lines[i]:
                issues.append(
                    f"Line {i}: Avoid silent exception handling. Log or handle the error."
                )
    
    return issues


def main():
    """Run all validations on Databricks notebooks."""
    notebooks_dir = Path('databricks-notebooks')
    
    if not notebooks_dir.exists():
        print("No databricks-notebooks directory found.")
        return 0
    
    print("🔍 Validating Databricks notebooks before upload...\n")
    
    total_issues = 0
    notebooks = list(notebooks_dir.glob('*.py'))
    
    for notebook in notebooks:
        print(f"Checking {notebook.name}...")
        issues = []
        
        # Run all validators
        issues.extend(validate_notebook_syntax(notebook))
        issues.extend(validate_streaming_patterns(notebook))
        issues.extend(validate_imports(notebook))
        issues.extend(validate_databricks_specific(notebook))
        
        if issues:
            print(f"  ❌ Found {len(issues)} issue(s):")
            for issue in issues:
                print(f"    - {issue}")
            total_issues += len(issues)
        else:
            print(f"  ✅ No issues found")
    
    print(f"\n{'='*60}")
    
    if total_issues > 0:
        print(f"❌ Validation failed: {total_issues} total issue(s) found")
        print("\nFix these issues before uploading to Databricks:")
        print("  1. Add parentheses to method calls (e.g., query.exception())")
        print("  2. Add checkpoint locations to all streaming queries")
        print("  3. Replace processingTime/continuous triggers with availableNow")
        print("  4. Add missing imports")
        return 1
    else:
        print("✅ All notebooks passed validation!")
        print("Ready to upload to Databricks.")
        return 0


if __name__ == "__main__":
    sys.exit(main())