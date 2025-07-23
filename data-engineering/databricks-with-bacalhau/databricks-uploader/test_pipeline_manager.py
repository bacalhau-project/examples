#!/usr/bin/env python3
"""Unit tests for PipelineManager."""

import unittest
import tempfile
import os
import sqlite3
import json
from datetime import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline_manager import PipelineManager, PipelineType, PipelineConfig


class TestPipelineManager(unittest.TestCase):
    """Test cases for PipelineManager."""
    
    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.manager = PipelineManager(self.db_path)
    
    def tearDown(self):
        """Clean up temporary database."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_initialization(self):
        """Test that database is properly initialized."""
        # Check tables exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check pipeline_config table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='pipeline_config'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        # Check pipeline_executions table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='pipeline_executions'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        # Check default configuration
        cursor.execute("SELECT pipeline_type FROM pipeline_config WHERE id = 1")
        row = cursor.fetchone()
        self.assertEqual(row[0], 'raw')
        
        conn.close()
    
    def test_get_current_pipeline(self):
        """Test getting current pipeline configuration."""
        config = self.manager.get_current_pipeline()
        
        self.assertEqual(config.pipeline_type, PipelineType.RAW)
        self.assertTrue(config.is_active)
        self.assertIsNone(config.updated_by)
        self.assertIsNone(config.config_json)
    
    def test_set_pipeline(self):
        """Test setting pipeline configuration."""
        # Set to schematized
        config = self.manager.set_pipeline(
            pipeline_type=PipelineType.SCHEMATIZED,
            updated_by="test_user",
            config_json={"remove_nulls": ["field1", "field2"]}
        )
        
        self.assertEqual(config.pipeline_type, PipelineType.SCHEMATIZED)
        self.assertEqual(config.updated_by, "test_user")
        self.assertIsNotNone(config.config_json)
        self.assertEqual(config.config_json["remove_nulls"], ["field1", "field2"])
        
        # Verify it persisted
        config2 = self.manager.get_current_pipeline()
        self.assertEqual(config2.pipeline_type, PipelineType.SCHEMATIZED)
    
    def test_atomic_updates(self):
        """Test that pipeline updates are atomic."""
        def update_pipeline(pipeline_type):
            try:
                self.manager.set_pipeline(
                    pipeline_type=pipeline_type,
                    updated_by=f"thread_{pipeline_type.value}"
                )
                return True
            except Exception:
                return False
        
        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for ptype in [PipelineType.RAW, PipelineType.FILTERED, 
                         PipelineType.SCHEMATIZED, PipelineType.EMERGENCY]:
                futures.append(executor.submit(update_pipeline, ptype))
            
            results = [f.result() for f in as_completed(futures)]
        
        # All updates should succeed (SQLite handles serialization)
        self.assertTrue(all(results))
        
        # Final state should be one of the pipeline types
        final_config = self.manager.get_current_pipeline()
        self.assertIn(final_config.pipeline_type, 
                     [PipelineType.RAW, PipelineType.FILTERED,
                      PipelineType.SCHEMATIZED, PipelineType.EMERGENCY])
    
    def test_execution_tracking(self):
        """Test pipeline execution tracking."""
        # Start execution
        exec_id = self.manager.start_execution(PipelineType.RAW)
        self.assertIsInstance(exec_id, int)
        
        # Simulate processing
        time.sleep(0.1)
        
        # Complete execution
        self.manager.complete_execution(exec_id, records_processed=100)
        
        # Check history
        history = self.manager.get_execution_history(limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, exec_id)
        self.assertEqual(history[0].pipeline_type, PipelineType.RAW)
        self.assertEqual(history[0].status, "completed")
        self.assertEqual(history[0].records_processed, 100)
        self.assertIsNotNone(history[0].completed_at)
    
    def test_execution_with_error(self):
        """Test pipeline execution with error."""
        exec_id = self.manager.start_execution(PipelineType.FILTERED)
        
        # Complete with error
        error_msg = "Connection timeout"
        self.manager.complete_execution(
            exec_id, 
            records_processed=0,
            error_message=error_msg
        )
        
        history = self.manager.get_execution_history(limit=1)
        self.assertEqual(history[0].status, "failed")
        self.assertEqual(history[0].error_message, error_msg)
    
    def test_migrate_from_config(self):
        """Test migration from config file format."""
        # Test different config scenarios
        configs = [
            ({"enable_aggregate": True}, PipelineType.EMERGENCY),
            ({"enable_filter": True}, PipelineType.FILTERED),
            ({"enable_sanitize": True}, PipelineType.SCHEMATIZED),
            ({}, PipelineType.RAW),
        ]
        
        for config, expected_type in configs:
            self.manager.migrate_from_config(config)
            current = self.manager.get_current_pipeline()
            self.assertEqual(current.pipeline_type, expected_type)
            self.assertEqual(current.updated_by, "config_migration")
    
    def test_concurrent_reads(self):
        """Test that concurrent reads don't block each other."""
        read_times = []
        
        def read_pipeline():
            start = time.time()
            config = self.manager.get_current_pipeline()
            end = time.time()
            return end - start, config.pipeline_type
        
        # Run concurrent reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_pipeline) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]
        
        # All reads should complete quickly (< 0.1s each)
        for duration, ptype in results:
            self.assertLess(duration, 0.1)
            self.assertEqual(ptype, PipelineType.RAW)
    
    def test_singleton_constraint(self):
        """Test that only one configuration row can exist."""
        conn = sqlite3.connect(self.db_path)
        
        # Try to insert another row
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO pipeline_config (id, pipeline_type) 
                VALUES (2, 'raw')
            """)
        
        conn.close()


class TestPipelineManagerCLI(unittest.TestCase):
    """Test CLI functionality of PipelineManager."""
    
    def setUp(self):
        """Create temporary database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.temp_db.name
        self.temp_db.close()
    
    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_cli_commands(self):
        """Test that CLI commands work correctly."""
        import subprocess
        
        # Test get command
        result = subprocess.run(
            ["python", "pipeline_manager.py", "--db", self.db_path, "get"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Current pipeline: raw", result.stdout)
        
        # Test set command
        result = subprocess.run(
            ["python", "pipeline_manager.py", "--db", self.db_path, 
             "set", "filtered", "--by", "test_user"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Pipeline updated to: filtered", result.stdout)
        
        # Test history command
        result = subprocess.run(
            ["python", "pipeline_manager.py", "--db", self.db_path, 
             "history", "--limit", "5"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()