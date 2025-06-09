#!/usr/bin/env python3
"""Unit tests for the Databricks uploader functions."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import tempfile
import time
import yaml

# Add the parent directory to the path so we can import the uploader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlite_to_databricks_uploader import (
    upload_batch_via_file,
    quote_databricks_identifier,
    convert_timestamps_to_strings,
    ConfigWatcher
)


class TestUploaderFunctions(unittest.TestCase):
    """Test cases for uploader functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a sample DataFrame with various data types
        self.sample_df = pd.DataFrame({
            'reading_id': [1, 2, 3],
            'timestamp': ['2025-01-01 10:00:00', '2025-01-01 10:01:00', '2025-01-01 10:02:00'],
            'sensor_id': ['sensor_001', 'sensor_002', 'sensor_003'],
            'temperature': [25.5, 26.1, 24.9],
            'humidity': [65.2, 64.8, 66.0],
            'status_code': [200, 200, 200],
            'anomaly_flag': [0, 0, 1],
            'location': ['Building A', "O'Brien's Lab", 'Building C'],  # Test single quote escaping
            'synced': [1, 1, 0],
            'databricks_inserted_at': [datetime.now(), datetime.now(), datetime.now()]
        })
        
    def test_quote_databricks_identifier(self):
        """Test the quote_databricks_identifier function."""
        # Test normal identifier
        self.assertEqual(quote_databricks_identifier('column_name'), '`column_name`')
        
        # Test identifier with backticks
        self.assertEqual(quote_databricks_identifier('column`name'), '`column``name`')
        
        # Test identifier with multiple backticks
        self.assertEqual(quote_databricks_identifier('col`umn`name'), '`col``umn``name`')
    
    def test_convert_timestamps_to_strings(self):
        """Test the convert_timestamps_to_strings function."""
        # Create DataFrame with timestamp column
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': pd.to_datetime(['2025-01-01 10:00:00', '2025-01-01 11:00:00', '2025-01-01 12:00:00']),
            'name': ['test1', 'test2', 'test3']
        })
        
        # Convert timestamps
        result_df = convert_timestamps_to_strings(df)
        
        # Check that timestamp column is now string
        self.assertTrue(all(isinstance(x, str) for x in result_df['timestamp']))
        
        # Check format
        self.assertTrue(all('2025-01-01' in x for x in result_df['timestamp']))
        
        # Check other columns unchanged
        self.assertEqual(list(result_df['id']), [1, 2, 3])
        self.assertEqual(list(result_df['name']), ['test1', 'test2', 'test3'])
    
    def test_upload_batch_via_file_success(self):
        """Test successful upload_batch_via_file execution."""
        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        
        # Convert timestamps to strings first (as would happen in real usage)
        test_df = convert_timestamps_to_strings(self.sample_df)
        
        # Call the function
        result = upload_batch_via_file(
            test_df,
            '`sensor_data`.`readings_1_schematized`',
            mock_cursor,
            'schematized'
        )
        
        # Check that it returned True (success)
        self.assertTrue(result)
        
        # Check that execute was called
        self.assertTrue(mock_cursor.execute.called)
        
        # Check that INSERT statement was created correctly
        calls = mock_cursor.execute.call_args_list
        self.assertTrue(any('INSERT INTO' in str(call) for call in calls))
        
    def test_upload_batch_via_file_handles_special_characters(self):
        """Test that upload_batch_via_file properly escapes special characters."""
        # Create DataFrame with special characters
        df = pd.DataFrame({
            'id': [1],
            'name': ["O'Brien's \"Test\" Data"],  # Single and double quotes
            'value': [123.45]
        })
        
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        
        # Call the function
        upload_batch_via_file(df, '`test`.`table`', mock_cursor, 'test')
        
        # Get the SQL that was executed
        sql_call = mock_cursor.execute.call_args[0][0]
        
        # Check that single quotes are escaped
        self.assertIn("O''Brien", sql_call)
        
    def test_upload_batch_via_file_handles_null_values(self):
        """Test that upload_batch_via_file properly handles NULL values."""
        # Create DataFrame with NULL values
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['test', None, 'test3'],
            'value': [123.45, 456.78, None]
        })
        
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        
        # Call the function
        upload_batch_via_file(df, '`test`.`table`', mock_cursor, 'test')
        
        # Get the SQL that was executed
        sql_call = mock_cursor.execute.call_args[0][0]
        
        # Check that NULL is used (not 'None' or 'NULL' as string)
        self.assertIn('NULL', sql_call)
        self.assertNotIn("'NULL'", sql_call)
        self.assertNotIn("'None'", sql_call)
    
    def test_upload_batch_via_file_error_handling(self):
        """Test that upload_batch_via_file handles errors properly."""
        # Mock cursor that raises an exception
        mock_cursor = Mock()
        mock_cursor.execute = Mock(side_effect=Exception("Database error"))
        
        # Call the function
        result = upload_batch_via_file(
            self.sample_df,
            '`sensor_data`.`readings_1_schematized`',
            mock_cursor,
            'schematized'
        )
        
        # Check that it returned False (failure)
        self.assertFalse(result)
    
    def test_upload_batch_via_file_batching(self):
        """Test that upload_batch_via_file correctly batches large datasets."""
        # Create a large DataFrame (1000 rows to test batching at 500)
        large_df = pd.DataFrame({
            'id': range(1000),
            'value': [f'value_{i}' for i in range(1000)]
        })
        
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        
        # Call the function
        upload_batch_via_file(large_df, '`test`.`table`', mock_cursor, 'test')
        
        # Check that execute was called multiple times (for batching)
        # With 1000 rows and batch size of 500, should be 2 calls
        self.assertEqual(mock_cursor.execute.call_count, 2)
        


    def test_timestamp_handling_in_state_update(self):
        """Test that timestamps are properly handled when updating state."""
        # Create DataFrame with timestamp column
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': pd.to_datetime(['2025-01-01 10:00:00', '2025-01-01 11:00:00', '2025-01-01 12:00:00']),
            'value': [10, 20, 30]
        })
        
        # Get max timestamp before conversion
        max_ts = pd.to_datetime(df['timestamp'].max())
        
        # Convert timestamps to strings
        df_converted = convert_timestamps_to_strings(df)
        
        # Verify that the max timestamp from string can be parsed back
        max_ts_from_string = pd.to_datetime(df_converted['timestamp'].max())
        
        # They should be equal (within microsecond precision)
        self.assertEqual(max_ts.strftime('%Y-%m-%d %H:%M:%S'), 
                        max_ts_from_string.strftime('%Y-%m-%d %H:%M:%S'))


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios."""
    
    @patch('databricks.sql.connect')
    def test_end_to_end_upload_simulation(self, mock_connect):
        """Simulate an end-to-end upload scenario."""
        # Mock the database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Create test data
        test_df = pd.DataFrame({
            'reading_id': range(250),  # More than batch size
            'sensor_id': [f'sensor_{i%10:03d}' for i in range(250)],
            'temperature': np.random.uniform(20, 30, 250),
            'timestamp': pd.date_range('2025-01-01', periods=250, freq='1min')
        })
        
        # Convert timestamps
        test_df = convert_timestamps_to_strings(test_df)
        
        # Perform upload
        result = upload_batch_via_file(
            test_df,
            '`sensor_data`.`readings_1_schematized`',
            mock_cursor,
            'schematized'
        )
        
        # Verify success
        self.assertTrue(result)
        
        # Verify batching occurred (250 rows / 500 batch size = 1 batch)
        self.assertEqual(mock_cursor.execute.call_count, 1)
        
        # Verify SQL structure
        for call in mock_cursor.execute.call_args_list:
            sql = call[0][0]
            self.assertIn('INSERT INTO', sql)
            self.assertIn('VALUES', sql)
            self.assertIn('`sensor_data`.`readings_1_schematized`', sql)


class TestConfigWatcher(unittest.TestCase):
    """Test cases for ConfigWatcher functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary config file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.config_path = self.temp_file.name
        
        # Write initial config
        self.initial_config = {
            'processing_mode': 'schematized',
            'interval': 300,
            'max_batch_size': 500
        }
        yaml.dump(self.initial_config, self.temp_file)
        self.temp_file.close()
        
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.config_path):
            os.unlink(self.config_path)
    
    def test_config_watcher_initialization(self):
        """Test that ConfigWatcher initializes correctly."""
        watcher = ConfigWatcher(self.config_path)
        
        # Check that initial config is loaded
        self.assertEqual(watcher.get('processing_mode'), 'schematized')
        self.assertEqual(watcher.get('interval'), 300)
        self.assertEqual(watcher.get('max_batch_size'), 500)
    
    def test_config_watcher_detects_changes(self):
        """Test that ConfigWatcher detects file changes."""
        watcher = ConfigWatcher(self.config_path, check_interval=0.1)
        watcher.start()
        
        # Initial values
        self.assertEqual(watcher.get('processing_mode'), 'schematized')
        
        # Wait a bit to ensure watcher is running
        time.sleep(0.2)
        
        # Update the config file
        new_config = {
            'processing_mode': 'sanitized',
            'interval': 600,
            'max_batch_size': 1000
        }
        with open(self.config_path, 'w') as f:
            yaml.dump(new_config, f)
        
        # Wait for the watcher to detect the change
        time.sleep(0.3)
        
        # Check that config was updated
        self.assertEqual(watcher.get('processing_mode'), 'sanitized')
        self.assertEqual(watcher.get('interval'), 600)
        self.assertEqual(watcher.get('max_batch_size'), 1000)
        
        # Stop the watcher
        watcher.stop()
    
    def test_config_watcher_handles_missing_file(self):
        """Test that ConfigWatcher handles missing config file gracefully."""
        watcher = ConfigWatcher('/non/existent/file.yaml')
        
        # Should not crash, should return defaults
        self.assertIsNone(watcher.get('processing_mode'))
        self.assertEqual(watcher.get('processing_mode', 'default'), 'default')
    
    def test_config_watcher_thread_safety(self):
        """Test that ConfigWatcher is thread-safe."""
        watcher = ConfigWatcher(self.config_path)
        watcher.start()
        
        # Simulate concurrent access
        results = []
        
        def get_config():
            for _ in range(100):
                config = watcher.get_all()
                results.append(config)
                time.sleep(0.001)
        
        # Start multiple threads
        import threading
        threads = []
        for _ in range(5):
            t = threading.Thread(target=get_config)
            threads.append(t)
            t.start()
        
        # Update config while threads are running
        time.sleep(0.05)
        new_config = {'processing_mode': 'aggregated'}
        with open(self.config_path, 'w') as f:
            yaml.dump(new_config, f)
        
        # Wait for threads to complete
        for t in threads:
            t.join()
        
        # All results should be valid configs
        self.assertTrue(all(isinstance(r, dict) for r in results))
        
        watcher.stop()
    
    def test_config_watcher_handles_invalid_yaml(self):
        """Test that ConfigWatcher handles invalid YAML gracefully."""
        watcher = ConfigWatcher(self.config_path)
        watcher.start()
        
        # Write invalid YAML
        with open(self.config_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        time.sleep(0.2)
        
        # Should still have the old config
        self.assertEqual(watcher.get('processing_mode'), 'schematized')
        
        watcher.stop()


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)