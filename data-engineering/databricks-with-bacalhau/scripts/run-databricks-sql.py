#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sql-connector",
#   "python-dotenv",
#   "rich",
#   "click",
# ]
# ///

"""
Execute SQL commands on Databricks SQL warehouse.

This script allows you to run SQL commands directly without using the UI.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Any

import click
from databricks import sql
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()


def get_connection():
    """Create Databricks SQL connection."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/").replace("https://", "")
    token = os.getenv("DATABRICKS_TOKEN", "")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
    
    if not all([host, token, http_path]):
        console.print("[red]Error: DATABRICKS_HOST, DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH must be set[/red]")
        sys.exit(1)
    
    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token
    )


def execute_sql(query: str, fetch_results: bool = True) -> Optional[List[Any]]:
    """Execute SQL query and optionally fetch results."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        
        if fetch_results and cursor.description:
            # Fetch all results
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return {"columns": columns, "rows": results}
        else:
            return None
            
    finally:
        cursor.close()
        conn.close()


def display_results(results: dict):
    """Display query results in a nice table."""
    if not results or not results["rows"]:
        console.print("[yellow]No results returned[/yellow]")
        return
    
    table = Table()
    
    # Add columns
    for col in results["columns"]:
        table.add_column(col, style="cyan")
    
    # Add rows
    for row in results["rows"]:
        table.add_row(*[str(val) for val in row])
    
    console.print(table)


@click.command()
@click.option('--query', '-q', help='SQL query to execute')
@click.option('--file', '-f', type=click.Path(exists=True), help='SQL file to execute')
@click.option('--command', '-c', help='Single SQL command (DDL/DML)')
@click.option('--catalog', help='Set current catalog')
@click.option('--database', help='Set current database')
def main(query: Optional[str], file: Optional[str], command: Optional[str], 
         catalog: Optional[str], database: Optional[str]):
    """Execute SQL on Databricks SQL warehouse."""
    
    console.print("[bold blue]Databricks SQL Executor[/bold blue]")
    console.print("=" * 50)
    
    # Set catalog/database if specified
    if catalog or database:
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if catalog:
                cursor.execute(f"USE CATALOG {catalog}")
                console.print(f"[green]✓ Using catalog: {catalog}[/green]")
            
            if database:
                cursor.execute(f"USE DATABASE {database}")
                console.print(f"[green]✓ Using database: {database}[/green]")
        finally:
            cursor.close()
            conn.close()
    
    # Determine what to execute
    sql_to_execute = None
    
    if query:
        sql_to_execute = query
    elif file:
        sql_to_execute = Path(file).read_text()
    elif command:
        sql_to_execute = command
    else:
        # Interactive mode
        console.print("\n[yellow]Enter SQL query (end with ';' on a new line):[/yellow]")
        lines = []
        while True:
            line = input()
            if line.strip() == ';':
                break
            lines.append(line)
        sql_to_execute = '\n'.join(lines)
    
    if sql_to_execute:
        # Show query
        console.print("\n[bold]Executing SQL:[/bold]")
        syntax = Syntax(sql_to_execute, "sql", theme="monokai", line_numbers=True)
        console.print(syntax)
        
        # Execute
        try:
            results = execute_sql(sql_to_execute)
            
            if results:
                console.print("\n[bold]Results:[/bold]")
                display_results(results)
            else:
                console.print("\n[green]✓ Query executed successfully[/green]")
                
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")


if __name__ == "__main__":
    main()