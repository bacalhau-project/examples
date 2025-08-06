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
Atomic Pipeline Controller for Databricks S3 Pipeline

This script provides atomic read/write operations for managing pipeline
configuration in the sensor SQLite database. It ensures no conflicts
with the uploader by using proper database transactions and locking.
"""

import sqlite3
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
import click
from tabulate import tabulate
import time
import logging
import sys
import os

# Add parent directory to path to import from databricks-uploader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'databricks-uploader')))
from config_db import get_config_db_path

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only show warnings and errors


class PipelineType(str, Enum):
    """Valid pipeline types."""
    RAW = "raw"
    SCHEMATIZED = "schematized"
    AGGREGATED = "aggregated"
    EMERGENCY = "emergency"
    REGIONAL = "regional"


class AtomicPipelineManager:
    """Manages pipeline configuration with atomic database operations."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        # Ensure pipeline_config table exists
        self._init_database()
    
    def _init_database(self):
        """Initialize the pipeline configuration table if it doesn't exist."""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_type TEXT NOT NULL CHECK(pipeline_type IN ('raw', 'schematized', 'aggregated', 'emergency', 'regional')),
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT,
                    metadata TEXT
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_config_updated_at 
                ON pipeline_config(updated_at DESC)
            """)
            
            # Check if there's any configuration
            cursor = conn.execute("SELECT COUNT(*) FROM pipeline_config")
            if cursor.fetchone()[0] == 0:
                # Insert default configuration
                conn.execute("""
                    INSERT INTO pipeline_config (pipeline_type, updated_by, metadata)
                    VALUES (?, ?, ?)
                """, (PipelineType.RAW, 'system', json.dumps({})))
            
            conn.commit()
    
    def get_current_pipeline(self) -> Dict:
        """Get the current pipeline configuration atomically."""
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("""
                        SELECT pipeline_type, updated_at, updated_by, metadata
                        FROM pipeline_config
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """)
                    row = cursor.fetchone()
                    
                    if row:
                        return {
                            'pipeline_type': row['pipeline_type'],
                            'updated_at': row['updated_at'],
                            'updated_by': row['updated_by'],
                            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                        }
                    return None
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
    
    def set_pipeline(self, pipeline_type: PipelineType) -> bool:
        """Set the pipeline type atomically."""
        max_retries = 5
        retry_delay = 0.1
        
        metadata = {
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute("BEGIN IMMEDIATE")  # Acquire write lock immediately
                    
                    # Insert new configuration
                    conn.execute("""
                        INSERT INTO pipeline_config (pipeline_type, updated_by, metadata)
                        VALUES (?, ?, ?)
                    """, (pipeline_type, 'system', json.dumps(metadata)))
                    
                    conn.commit()
                    # Silent success - the CLI will show the message
                    return True
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
        
        return False
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get pipeline change history atomically."""
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("""
                        SELECT id, pipeline_type, updated_at, updated_by, metadata
                        FROM pipeline_config
                        ORDER BY updated_at DESC
                        LIMIT ?
                    """, (limit,))
                    
                    history = []
                    for row in cursor:
                        history.append({
                            'id': row['id'],
                            'pipeline_type': row['pipeline_type'],
                            'updated_at': row['updated_at'],
                            'updated_by': row['updated_by'],
                            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                        })
                    
                    return history
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
        
        return []


@click.group()
@click.option('--db', help='Path to SQLite database (defaults to shared config DB)')
@click.pass_context
def cli(ctx, db):
    """Pipeline Controller for Databricks S3 Pipeline.
    
    Provides atomic operations for managing pipeline configuration.
    """
    ctx.ensure_object(dict)
    
    # If --db is not provided, use the shared config database
    if db is None:
        db = get_config_db_path()
        # Create parent directory if needed
        db_path = Path(db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty database file if it doesn't exist
        if not db_path.exists():
            db_path.touch()
            click.echo(f"Created config database: {db}")
    
    ctx.obj['manager'] = AtomicPipelineManager(db)


@cli.command()
@click.pass_context
def get(ctx):
    """Get current pipeline configuration."""
    manager = ctx.obj['manager']
    config = manager.get_current_pipeline()
    
    if config:
        click.echo(f"Current pipeline: {config['pipeline_type']}")
        click.echo(f"Updated at: {config['updated_at']}")
    else:
        click.echo("No pipeline configuration found")


@cli.command()
@click.argument('pipeline_type', type=click.Choice([t.value for t in PipelineType]))
@click.pass_context
def set(ctx, pipeline_type):
    """Set pipeline type with atomic operation."""
    manager = ctx.obj['manager']
    
    # Get current config first
    current = manager.get_current_pipeline()
    if current and current['pipeline_type'] == pipeline_type:
        click.echo(f"Pipeline is already set to: {pipeline_type}")
        return
    
    # Set new pipeline type
    success = manager.set_pipeline(PipelineType(pipeline_type))
    
    if success:
        click.echo(f"✅ Pipeline updated to: {pipeline_type}")
    else:
        click.echo(f"❌ Failed to update pipeline", err=True)
        ctx.exit(1)


@cli.command()
@click.option('--limit', default=20, help='Number of entries to show')
@click.option('--format', 'output_format', 
              type=click.Choice(['table', 'json']), 
              default='table',
              help='Output format')
@click.pass_context
def history(ctx, limit, output_format):
    """Show pipeline change history."""
    manager = ctx.obj['manager']
    history = manager.get_history(limit)
    
    if not history:
        click.echo("No history found")
        return
    
    if output_format == 'json':
        click.echo(json.dumps(history, indent=2))
    else:
        # Format for table display
        table_data = []
        for entry in history:
            table_data.append([
                entry['id'],
                entry['pipeline_type'],
                entry['updated_at']
            ])
        
        headers = ['ID', 'Pipeline Type', 'Updated At']
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))


@cli.command()
@click.pass_context
def monitor(ctx):
    """Monitor pipeline changes in real-time."""
    manager = ctx.obj['manager']
    last_config = manager.get_current_pipeline()
    
    click.echo("Monitoring pipeline changes (Ctrl+C to stop)...")
    click.echo(f"Current: {last_config['pipeline_type']}")
    
    try:
        while True:
            time.sleep(2)  # Check every 2 seconds
            current_config = manager.get_current_pipeline()
            
            if current_config['updated_at'] != last_config['updated_at']:
                click.echo(f"\n🔄 Pipeline changed!")
                click.echo(f"   From: {last_config['pipeline_type']}")
                click.echo(f"   To: {current_config['pipeline_type']}")
                click.echo(f"   At: {current_config['updated_at']}")
                
                last_config = current_config
                
    except KeyboardInterrupt:
        click.echo("\nMonitoring stopped")


if __name__ == '__main__':
    cli()