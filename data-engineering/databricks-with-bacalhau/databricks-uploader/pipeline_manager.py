#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Minimal Pipeline Manager for Autoloader - handles pipeline configuration and tracking.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class PipelineManager:
    """Minimal pipeline manager for Autoloader integration."""
    
    def __init__(self, db_path: str = "pipeline_config.db"):
        """Initialize pipeline manager."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the pipeline database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_config (
                id INTEGER PRIMARY KEY,
                pipeline_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_executions (
                id INTEGER PRIMARY KEY,
                pipeline_type TEXT NOT NULL,
                records_processed INTEGER,
                s3_locations TEXT,
                job_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current pipeline configuration from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the most recent active configuration
        cursor.execute("""
            SELECT pipeline_type, created_at, created_by 
            FROM pipeline_config 
            WHERE is_active = 1
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'type': result[0],
                'created_at': result[1],
                'source': result[2] or 'database'
            }
        else:
            # Fallback to environment or default
            pipeline_type = os.getenv('PIPELINE_TYPE', 'raw')
            return {
                'type': pipeline_type,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'source': 'environment' if os.getenv('PIPELINE_TYPE') else 'default'
            }
    
    def record_execution(
        self, 
        pipeline_type: str, 
        records_processed: int, 
        s3_locations: List[str], 
        job_id: str = None
    ):
        """Record a pipeline execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO pipeline_executions 
            (pipeline_type, records_processed, s3_locations, job_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pipeline_type,
            records_processed,
            json.dumps(s3_locations),
            job_id,
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def set_pipeline_type(self, pipeline_type: str, created_by: str = "autoloader_main"):
        """Set the active pipeline type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Deactivate all existing configs
        cursor.execute("UPDATE pipeline_config SET is_active = 0")
        
        # Add new active config
        cursor.execute("""
            INSERT INTO pipeline_config (pipeline_type, created_at, created_by, is_active)
            VALUES (?, ?, ?, 1)
        """, (
            pipeline_type,
            datetime.now(timezone.utc).isoformat(),
            created_by
        ))
        
        conn.commit()
        conn.close()
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pipeline_type, records_processed, s3_locations, job_id, created_at
            FROM pipeline_executions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'pipeline_type': row[0],
                'records_processed': row[1],
                's3_locations': json.loads(row[2]) if row[2] else [],
                'job_id': row[3],
                'created_at': row[4]
            })
        
        conn.close()
        return results

def main():
    """CLI interface for pipeline manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline Manager")
    parser.add_argument("--db", default="pipeline_config.db", help="Database path")
    parser.add_argument("action", choices=["get", "set", "history"], help="Action to perform")
    parser.add_argument("--type", help="Pipeline type to set")
    parser.add_argument("--by", default="cli", help="Created by")
    
    args = parser.parse_args()
    
    manager = PipelineManager(args.db)
    
    if args.action == "get":
        config = manager.get_current_config()
        print(f"Current pipeline type: {config['type']}")
        print(f"Source: {config['source']}")
    
    elif args.action == "set":
        if not args.type:
            print("Error: --type required for set action")
            return 1
        manager.set_pipeline_type(args.type, args.by)
        print(f"Pipeline type set to: {args.type}")
    
    elif args.action == "history":
        history = manager.get_execution_history()
        print(f"Recent executions ({len(history)}):")
        for exec in history[:10]:
            print(f"  {exec['created_at']}: {exec['pipeline_type']} - {exec['records_processed']} records")
    
    return 0

if __name__ == "__main__":
    exit(main())
