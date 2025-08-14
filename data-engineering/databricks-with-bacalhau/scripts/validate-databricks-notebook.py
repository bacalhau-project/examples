#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich",
#   "click",
#   "libcst",
# ]
# ///

"""
Validate Databricks notebooks for syntax errors before uploading.

This script:
1. Parses Databricks notebook format
2. Extracts Python code cells
3. Validates Python syntax
4. Checks for common Databricks-specific issues
5. Reports errors with line numbers
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

import click
import libcst as cst
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

console = Console()


class NotebookCell:
    """Represents a cell in a Databricks notebook."""

    def __init__(self, cell_type: str, content: str, line_start: int):
        self.type = cell_type  # 'code', 'markdown', 'magic'
        self.content = content
        self.line_start = line_start
        self.line_end = line_start + len(content.splitlines())


class DatabricksNotebookParser:
    """Parse Databricks notebook format."""

    COMMAND_PATTERN = re.compile(r"^# COMMAND ----------\s*$")
    MAGIC_PATTERN = re.compile(r"^# MAGIC (.+)$")

    def parse(self, content: str) -> List[NotebookCell]:
        """Parse notebook content into cells."""
        lines = content.splitlines()
        cells = []
        current_cell_lines = []
        current_cell_start = 1
        in_magic_block = False

        for i, line in enumerate(lines, 1):
            if self.COMMAND_PATTERN.match(line):
                if current_cell_lines:
                    cell_content = "\n".join(current_cell_lines)
                    cell_type = "magic" if in_magic_block else "code"
                    cells.append(NotebookCell(cell_type, cell_content, current_cell_start))
                current_cell_lines = []
                current_cell_start = i + 1
                in_magic_block = False
            elif self.MAGIC_PATTERN.match(line):
                magic_content = self.MAGIC_PATTERN.match(line).group(1)
                current_cell_lines.append(magic_content)
                in_magic_block = True
            else:
                current_cell_lines.append(line)

        if current_cell_lines:
            cell_content = "\n".join(current_cell_lines)
            cell_type = "magic" if in_magic_block else "code"
            cells.append(NotebookCell(cell_type, cell_content, current_cell_start))

        return cells


class NotebookValidator:
    """Validate Databricks notebook syntax."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_python_syntax(self, code: str, line_offset: int = 0) -> List[Tuple[int, str]]:
        """Validate Python syntax and return errors."""
        errors = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            line_num = (e.lineno or 1) + line_offset - 1
            errors.append((line_num, f"SyntaxError: {e.msg}"))
        except Exception as e:
            errors.append((line_offset, f"Parse error: {str(e)}"))

        return errors

    def validate_imports(self, code: str, line_offset: int = 0) -> List[Tuple[int, str]]:
        """Check for common import issues in Databricks."""
        warnings = []

        problematic_imports = {
            "pyspark": "PySpark is pre-imported in Databricks",
            "databricks.connect": "Databricks Connect not needed in notebooks",
        }

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for pkg, msg in problematic_imports.items():
                            if alias.name.startswith(pkg):
                                line_num = node.lineno + line_offset - 1
                                warnings.append((line_num, f"Warning: {msg}"))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for pkg, msg in problematic_imports.items():
                            if node.module.startswith(pkg):
                                line_num = node.lineno + line_offset - 1
                                warnings.append((line_num, f"Warning: {msg}"))
        except:
            pass

        return warnings

    def validate_databricks_specifics(
        self, code: str, line_offset: int = 0
    ) -> List[Tuple[int, str]]:
        """Check for Databricks-specific issues."""
        warnings = []
        lines = code.splitlines()

        for i, line in enumerate(lines, 1):
            line_num = i + line_offset - 1

            if "dbutils" in line and "import" in line:
                warnings.append((line_num, "Warning: dbutils is pre-imported, no need to import"))

            if "spark.conf.set" in line:
                warnings.append(
                    (line_num, "Info: Spark config changes may require cluster restart")
                )

            if re.search(r'open\(["\']/', line):
                warnings.append((line_num, "Warning: Local file paths may not work in Databricks"))

            if "os.environ" in line:
                warnings.append(
                    (line_num, "Warning: Environment variables should be set via cluster config")
                )

        return warnings

    def validate_cell(
        self, cell: NotebookCell
    ) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
        """Validate a single notebook cell."""
        errors = []
        warnings = []

        if cell.type == "code":
            cleaned_code = self.clean_code(cell.content)

            errors.extend(self.validate_python_syntax(cleaned_code, cell.line_start))
            warnings.extend(self.validate_imports(cleaned_code, cell.line_start))
            warnings.extend(self.validate_databricks_specifics(cleaned_code, cell.line_start))

        return errors, warnings

    def clean_code(self, code: str) -> str:
        """Remove Databricks-specific comments and clean code."""
        lines = []
        for line in code.splitlines():
            if not line.strip().startswith("# Databricks notebook source"):
                lines.append(line)
        return "\n".join(lines)

    def validate_notebook(self, notebook_path: Path) -> bool:
        """Validate entire notebook and return success status."""
        content = notebook_path.read_text()
        parser = DatabricksNotebookParser()
        cells = parser.parse(content)

        all_errors = []
        all_warnings = []

        for cell in cells:
            errors, warnings = self.validate_cell(cell)
            all_errors.extend(errors)
            all_warnings.extend(warnings)

        self.errors = sorted(all_errors, key=lambda x: x[0])
        self.warnings = sorted(all_warnings, key=lambda x: x[0])

        return len(self.errors) == 0


def print_validation_results(
    notebook_path: Path,
    errors: List[Tuple[int, str]],
    warnings: List[Tuple[int, str]],
    show_context: bool = False,
):
    """Print validation results in a formatted table."""

    console.print(f"\n[bold]Validation Results for {notebook_path.name}[/bold]")
    console.print("=" * 60)

    if errors:
        console.print("\n[bold red]❌ Errors Found:[/bold red]")
        error_table = Table(show_header=True, header_style="bold red")
        error_table.add_column("Line", style="red", width=8)
        error_table.add_column("Error", style="red")

        for line_num, error in errors:
            error_table.add_row(str(line_num), error)

        console.print(error_table)

        if show_context:
            console.print("\n[bold]Error Context:[/bold]")
            content = notebook_path.read_text()
            lines = content.splitlines()

            for line_num, error in errors[:3]:  # Show first 3 errors
                console.print(f"\n[red]Line {line_num}: {error}[/red]")
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 2)

                for i in range(start, end):
                    prefix = ">>> " if i == line_num - 1 else "    "
                    console.print(f"{prefix}{i + 1:4d}: {lines[i]}")

    if warnings:
        console.print("\n[bold yellow]⚠️  Warnings:[/bold yellow]")
        warning_table = Table(show_header=True, header_style="bold yellow")
        warning_table.add_column("Line", style="yellow", width=8)
        warning_table.add_column("Warning", style="yellow")

        for line_num, warning in warnings:
            warning_table.add_row(str(line_num), warning)

        console.print(warning_table)

    if not errors and not warnings:
        console.print("[bold green]✅ No issues found![/bold green]")

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Errors: {len(errors)}")
    console.print(f"  Warnings: {len(warnings)}")

    return len(errors) == 0


@click.command()
@click.argument("notebook", type=click.Path(exists=True, path_type=Path))
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--show-context", is_flag=True, help="Show code context for errors")
@click.option("--quiet", is_flag=True, help="Only show summary")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
def main(notebook: Path, strict: bool, show_context: bool, quiet: bool, output_json: bool):
    """Validate Databricks notebook syntax before uploading."""

    if not quiet and not output_json:
        console.print("[bold blue]Databricks Notebook Validator[/bold blue]")
        console.print("=" * 60)

    validator = NotebookValidator()
    is_valid = validator.validate_notebook(notebook)

    if output_json:
        import json

        result = {
            "valid": is_valid and (not strict or len(validator.warnings) == 0),
            "errors": [{"line": l, "message": m} for l, m in validator.errors],
            "warnings": [{"line": l, "message": m} for l, m in validator.warnings],
        }
        print(json.dumps(result, indent=2))
    elif not quiet:
        print_validation_results(notebook, validator.errors, validator.warnings, show_context)

    if strict and validator.warnings:
        is_valid = False

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
