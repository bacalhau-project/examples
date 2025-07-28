#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic",
# ]
# ///

"""
Pipeline configuration manager using SQLite for atomic, concurrent pipeline selection.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pathlib import Path
from contextlib import contextmanager
import logging
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PipelineType(str, Enum):
    """Valid pipeline types."""
    RAW = "raw"
    SCHEMATIZED = "schematized"
    FILTERED = "filtered"
    EMERGENCY = "emergency"


class PipelineConfig(BaseModel):
    """Pipeline configuration model."""
    pipeline_type: PipelineType
    updated_at: datetime = Field(default_factory=datetime.now)
    updated_by: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_active: bool = True

    @field_validator('config_json', mode='before')
    def parse_json_string(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class PipelineExecution(BaseModel):
    """Pipeline execution record."""
    id: Optional[int] = None
    pipeline_type: PipelineType
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    status: Literal["running", "completed", "failed"] = "running"
    error_message: Optional[str] = None


class PipelineManager:
    """Manages pipeline configuration and execution tracking in SQLite."""
    
    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None):
        """Initialize the pipeline manager.
        
        Args:
            db_path: Path to SQLite database
            logger: Optional logger instance
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Create pipeline configuration table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    pipeline_type TEXT NOT NULL CHECK (pipeline_type IN ('raw', 'schematized', 'filtered', 'emergency')),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT,
                    config_json TEXT,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Create pipeline execution history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_type TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    records_processed INTEGER DEFAULT 0,
                    status TEXT CHECK (status IN ('running', 'completed', 'failed')),
                    error_message TEXT
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_executions_started_at 
                ON pipeline_executions(started_at)
            """)
            
            # Insert default config if not exists
            conn.execute("""
                INSERT OR IGNORE INTO pipeline_config (id, pipeline_type) 
                VALUES (1, 'raw')
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
        try:
            yield conn
        finally:
            conn.close()
    
    def get_current_pipeline(self) -> PipelineConfig:
        """Get the current pipeline configuration.
        
        Returns:
            Current pipeline configuration
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_config WHERE id = 1 AND is_active = 1"
            ).fetchone()
            
            if not row:
                raise ValueError("No active pipeline configuration found")
            
            return PipelineConfig(
                pipeline_type=row['pipeline_type'],
                updated_at=datetime.fromisoformat(row['updated_at']),
                updated_by=row['updated_by'],
                config_json=json.loads(row['config_json']) if row['config_json'] else None,
                is_active=bool(row['is_active'])
            )
    
    def set_pipeline(self, 
                    pipeline_type: PipelineType,
                    updated_by: Optional[str] = None,
                    config_json: Optional[Dict[str, Any]] = None) -> PipelineConfig:
        """Atomically set the pipeline type.
        
        Args:
            pipeline_type: New pipeline type
            updated_by: Who is making this change
            config_json: Optional configuration data
            
        Returns:
            Updated pipeline configuration
        """
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Update the configuration
                conn.execute("""
                    UPDATE pipeline_config 
                    SET pipeline_type = ?, 
                        updated_at = ?, 
                        updated_by = ?,
                        config_json = ?
                    WHERE id = 1
                """, (
                    pipeline_type.value,
                    datetime.now().isoformat(),
                    updated_by,
                    json.dumps(config_json) if config_json else None
                ))
                
                conn.commit()
                self.logger.info(f"Pipeline type updated to: {pipeline_type.value}")
                
                return self.get_current_pipeline()
                
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to update pipeline: {e}")
                raise
    
    def start_execution(self, pipeline_type: Optional[PipelineType] = None) -> int:
        """Record the start of a pipeline execution.
        
        Args:
            pipeline_type: Pipeline type (uses current if not specified)
            
        Returns:
            Execution ID
        """
        if pipeline_type is None:
            pipeline_type = self.get_current_pipeline().pipeline_type
        
        # Handle both string and PipelineType enum
        if isinstance(pipeline_type, str):
            pipeline_value = pipeline_type
        else:
            pipeline_value = pipeline_type.value
            
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO pipeline_executions (pipeline_type, status)
                VALUES (?, 'running')
            """, (pipeline_value,))
            
            conn.commit()
            return cursor.lastrowid
    
    def complete_execution(self, 
                          execution_id: int, 
                          records_processed: int,
                          error_message: Optional[str] = None):
        """Mark a pipeline execution as complete.
        
        Args:
            execution_id: ID from start_execution
            records_processed: Number of records processed
            error_message: Error message if failed
        """
        status = "failed" if error_message else "completed"
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE pipeline_executions
                SET completed_at = ?,
                    records_processed = ?,
                    status = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                records_processed,
                status,
                error_message,
                execution_id
            ))
            
            conn.commit()
            self.logger.info(f"Execution {execution_id} {status} with {records_processed} records")
    
    def get_execution_history(self, limit: int = 10) -> list[PipelineExecution]:
        """Get recent execution history.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of recent pipeline executions
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM pipeline_executions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                PipelineExecution(
                    id=row['id'],
                    pipeline_type=row['pipeline_type'],
                    started_at=datetime.fromisoformat(row['started_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    records_processed=row['records_processed'],
                    status=row['status'],
                    error_message=row['error_message']
                )
                for row in rows
            ]
    
    def migrate_from_config(self, config: Dict[str, Any]):
        """Migrate pipeline settings from config file to database.
        
        Args:
            config: Configuration dictionary
        """
        # Determine pipeline type from config flags
        if config.get('enable_aggregate'):
            pipeline_type = PipelineType.EMERGENCY
        elif config.get('enable_filter'):
            pipeline_type = PipelineType.FILTERED
        elif config.get('enable_sanitize'):
            pipeline_type = PipelineType.SCHEMATIZED
        else:
            pipeline_type = PipelineType.RAW
        
        # Extract relevant config for the pipeline
        config_json = {}
        if pipeline_type == PipelineType.SCHEMATIZED:
            config_json = config.get('sanitize_config', {})
        elif pipeline_type == PipelineType.FILTERED:
            config_json = config.get('filter_config', {})
        elif pipeline_type == PipelineType.EMERGENCY:
            config_json = config.get('aggregate_config', {})
        
        self.set_pipeline(
            pipeline_type=pipeline_type,
            updated_by="config_migration",
            config_json=config_json
        )
        
        self.logger.info(f"Migrated config to database: {pipeline_type.value}")


# CLI interface for managing pipelines
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage pipeline configuration")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Get current pipeline
    subparsers.add_parser("get", help="Get current pipeline configuration")
    
    # Set pipeline
    set_parser = subparsers.add_parser("set", help="Set pipeline type")
    set_parser.add_argument("type", choices=["raw", "schematized", "filtered", "emergency"])
    set_parser.add_argument("--by", help="Who is making this change")
    
    # History
    history_parser = subparsers.add_parser("history", help="Show execution history")
    history_parser.add_argument("--limit", type=int, default=10, help="Number of records")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create manager
    manager = PipelineManager(args.db)
    
    if args.command == "get":
        config = manager.get_current_pipeline()
        print(f"Current pipeline: {config.pipeline_type.value}")
        print(f"Updated at: {config.updated_at}")
        print(f"Updated by: {config.updated_by or 'N/A'}")
        if config.config_json:
            print(f"Config: {json.dumps(config.config_json, indent=2)}")
    
    elif args.command == "set":
        config = manager.set_pipeline(
            pipeline_type=PipelineType(args.type),
            updated_by=args.by
        )
        print(f"Pipeline updated to: {config.pipeline_type.value}")
    
    elif args.command == "history":
        history = manager.get_execution_history(limit=args.limit)
        for exec in history:
            print(f"\n[{exec.id}] {exec.pipeline_type.value} - {exec.status}")
            print(f"  Started: {exec.started_at}")
            if exec.completed_at:
                print(f"  Completed: {exec.completed_at}")
            print(f"  Records: {exec.records_processed}")
            if exec.error_message:
                print(f"  Error: {exec.error_message}")