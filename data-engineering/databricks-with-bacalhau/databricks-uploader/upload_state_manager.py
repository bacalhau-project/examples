#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "tabulate",
#     "python-dateutil",
# ]
# ///

"""
Upload State Manager for S3 Uploader

View and manage upload state stored in the SQLite database.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import click
from tabulate import tabulate
from dateutil import parser as date_parser


class UploadStateManager:
    """Manages upload state in the database."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
    
    def get_all_states(self):
        """Get all upload states from the database."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, table_name, scenario, last_timestamp, 
                   last_upload_at, last_batch_id, records_uploaded
            FROM upload_state
            ORDER BY last_upload_at DESC
        """)
        
        states = []
        for row in cursor:
            states.append({
                'id': row['id'],
                'table_name': row['table_name'],
                'scenario': row['scenario'],
                'last_timestamp': row['last_timestamp'],
                'last_upload_at': row['last_upload_at'],
                'last_batch_id': row['last_batch_id'],
                'records_uploaded': row['records_uploaded']
            })
        
        conn.close()
        return states
    
    def reset_state(self, table_name: str, scenario: str = None):
        """Reset upload state for a table/scenario."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        if scenario:
            conn.execute("""
                DELETE FROM upload_state 
                WHERE table_name = ? AND scenario = ?
            """, (table_name, scenario))
        else:
            conn.execute("""
                DELETE FROM upload_state 
                WHERE table_name = ?
            """, (table_name,))
        
        changes = conn.total_changes
        conn.commit()
        conn.close()
        
        return changes
    
    def set_timestamp(self, table_name: str, scenario: str, timestamp: str):
        """Manually set the last timestamp for a table/scenario."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Validate timestamp format
        try:
            date_parser.parse(timestamp)
        except:
            raise ValueError(f"Invalid timestamp format: {timestamp}")
        
        conn.execute("""
            INSERT OR REPLACE INTO upload_state 
            (table_name, scenario, last_timestamp, last_upload_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (table_name, scenario, timestamp))
        
        conn.commit()
        conn.close()


@click.group()
@click.option('--db', required=True, help='Path to SQLite database')
@click.pass_context
def cli(ctx, db):
    """Upload State Manager for S3 Uploader."""
    ctx.ensure_object(dict)
    ctx.obj['manager'] = UploadStateManager(db)


@cli.command()
@click.pass_context
def list(ctx):
    """List all upload states."""
    manager = ctx.obj['manager']
    states = manager.get_all_states()
    
    if not states:
        click.echo("No upload states found")
        return
    
    # Format for table display
    table_data = []
    for state in states:
        table_data.append([
            state['table_name'],
            state['scenario'],
            state['last_timestamp'],
            state['last_upload_at'],
            state['records_uploaded'] or 0
        ])
    
    headers = ['Table', 'Scenario', 'Last Timestamp', 'Last Upload', 'Records']
    click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))


@cli.command()
@click.argument('table_name')
@click.option('--scenario', '-s', help='Specific scenario to reset')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def reset(ctx, table_name, scenario, confirm):
    """Reset upload state for a table."""
    manager = ctx.obj['manager']
    
    if not confirm:
        if scenario:
            msg = f"Reset state for table '{table_name}' scenario '{scenario}'?"
        else:
            msg = f"Reset all states for table '{table_name}'?"
        
        if not click.confirm(msg):
            click.echo("Cancelled")
            return
    
    changes = manager.reset_state(table_name, scenario)
    
    if changes > 0:
        click.echo(f"✅ Reset {changes} state entries")
    else:
        click.echo("No states found to reset")


@cli.command()
@click.argument('table_name')
@click.argument('scenario')
@click.argument('timestamp')
@click.pass_context
def set_timestamp(ctx, table_name, scenario, timestamp):
    """Manually set the last timestamp for a table/scenario."""
    manager = ctx.obj['manager']
    
    try:
        manager.set_timestamp(table_name, scenario, timestamp)
        click.echo(f"✅ Set timestamp for {table_name}/{scenario} to: {timestamp}")
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)


if __name__ == '__main__':
    cli()