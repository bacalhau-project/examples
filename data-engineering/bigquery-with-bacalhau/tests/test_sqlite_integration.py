#!/usr/bin/env python3
"""
Test SQLite integration for BigQuery Uploader
Tests database connectivity, query functions, and data processing
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bigquery-uploader'))

# Mock the google.cloud.bigquery module before importing our module
from unittest.mock import Mock, patch, MagicMock
sys.modules['google.cloud.bigquery'] = Mock()
sys.modules['google.cloud'] = Mock()
sys.modules['google.api_core'] = Mock()
sys.modules['google.api_core.exceptions'] = Mock()

import bigquery_uploader_sqlite as uploader


class TestSQLiteIntegration(unittest.TestCase):
    """Test SQLite database integration"""
    
    def setUp(self):
        """Create a temporary SQLite database with test data"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Create test database schema
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                sensor_id TEXT,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                vibration REAL,
                voltage REAL,
                status_code INTEGER,
                anomaly_flag BOOLEAN,
                anomaly_type TEXT,
                synced BOOLEAN DEFAULT 0,
                firmware_version TEXT,
                model TEXT,
                manufacturer TEXT,
                serial_number TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                deployment_type TEXT,
                installation_date TEXT
            )
        ''')
        
        # Insert test data
        test_data = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=2)
        
        for i in range(20):
            timestamp = base_time + timedelta(minutes=i * 5)
            anomaly = i % 5 == 0  # Every 5th reading is an anomaly
            
            test_data.append((
                timestamp.isoformat(),
                f'SENSOR_{i % 3:03d}',  # 3 different sensors
                20.0 + (i % 10) * 0.5,  # Temperature
                45.0 + (i % 10) * 2,    # Humidity
                1013.0 + (i % 10) * 0.1,  # Pressure
                0.0,  # Vibration
                12.0 + (i % 10) * 0.01,  # Voltage
                0 if not anomaly else 1,  # Status code
                anomaly,  # Anomaly flag
                'spike' if anomaly else None,  # Anomaly type
                0,  # Not synced
                '1.4.2',  # Firmware version
                'EnvMonitor-3000',  # Model
                'SensorTech',  # Manufacturer
                f'SN{i:06d}',  # Serial number
                'Test Location',  # Location
                41.8781 + (i % 10) * 0.001,  # Latitude
                -87.6298 + (i % 10) * 0.001,  # Longitude
                'fixed',  # Deployment type
                '2024-01-01'  # Installation date
            ))
        
        conn.executemany('''
            INSERT INTO sensor_readings (
                timestamp, sensor_id, temperature, humidity, pressure, vibration,
                voltage, status_code, anomaly_flag, anomaly_type, synced,
                firmware_version, model, manufacturer, serial_number, location,
                latitude, longitude, deployment_type, installation_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
        
        conn.commit()
        conn.close()
        
        # Test configuration
        self.test_config = {
            'pipeline_mode': 'schematized',
            'chunk_size': 5,
            'project_id': 'test-project',
            'dataset': 'test_dataset',
            'node_id': 'test-node',
            'database': {
                'path': self.db_path,
                'table': 'sensor_readings',
                'sync_enabled': True
            },
            'tables': {
                'raw': 'raw_data',
                'schematized': 'sensor_data',
                'sanitized': 'sensor_data_sanitized',
                'aggregated': 'sensor_aggregates',
                'anomalies': 'sensor_anomalies'
            },
            'metadata': {
                'region': 'us-central1',
                'provider': 'gcp',
                'hostname': 'test-host'
            }
        }
    
    def tearDown(self):
        """Clean up temporary database"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_sqlite_connection(self):
        """Test SQLite connection creation"""
        conn = uploader.get_sqlite_connection(self.db_path)
        self.assertIsNotNone(conn)
        
        # Verify pragmas are set
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        self.assertEqual(result[0], 'wal')
        
        conn.close()
    
    def test_query_sensor_data(self):
        """Test querying sensor data from SQLite"""
        conn = uploader.get_sqlite_connection(self.db_path)
        
        # Test basic query
        df = uploader.query_sensor_data(conn, 5, 0, self.test_config)
        self.assertEqual(len(df), 5)
        self.assertIn('sensor_id', df.columns)
        self.assertIn('temperature', df.columns)
        self.assertIn('timestamp', df.columns)
        
        # Test with offset
        df2 = uploader.query_sensor_data(conn, 5, 5, self.test_config)
        self.assertEqual(len(df2), 5)
        self.assertNotEqual(df['id'].tolist(), df2['id'].tolist())
        
        conn.close()
    
    def test_query_with_timestamp_filter(self):
        """Test querying with timestamp filtering"""
        conn = uploader.get_sqlite_connection(self.db_path)
        
        # Get all data first
        df_all = uploader.query_sensor_data(conn, 100, 0, self.test_config)
        
        # Use middle timestamp as filter
        middle_timestamp = df_all['timestamp'].iloc[10]
        
        # Query with timestamp filter
        df_filtered = uploader.query_sensor_data(
            conn, 100, 0, self.test_config, last_timestamp=middle_timestamp
        )
        
        # Should have fewer records
        self.assertLess(len(df_filtered), len(df_all))
        
        # All timestamps should be after the filter
        self.assertTrue(all(df_filtered['timestamp'] > middle_timestamp))
        
        conn.close()
    
    def test_mark_as_synced(self):
        """Test marking records as synced"""
        conn = uploader.get_sqlite_connection(self.db_path)
        
        # Get unsynced records
        df = uploader.query_sensor_data(conn, 5, 0, self.test_config)
        record_ids = df['id'].tolist()
        
        # Mark as synced
        uploader.mark_as_synced(conn, record_ids, self.test_config)
        
        # Verify they are marked as synced
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(record_ids))
        cursor.execute(
            f"SELECT COUNT(*) FROM sensor_readings WHERE id IN ({placeholders}) AND synced = 1",
            record_ids
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, len(record_ids))
        
        # Query again - should not include synced records
        df2 = uploader.query_sensor_data(conn, 100, 0, self.test_config)
        self.assertFalse(any(id in df2['id'].tolist() for id in record_ids))
        
        conn.close()
    
    def test_process_raw_sensors(self):
        """Test raw sensor data processing"""
        conn = uploader.get_sqlite_connection(self.db_path)
        df = uploader.query_sensor_data(conn, 5, 0, self.test_config)
        
        processed = uploader.process_raw_sensors(df, self.test_config)
        
        # Check required fields
        self.assertIn('upload_time', processed.columns)
        self.assertIn('project_id', processed.columns)
        self.assertIn('region', processed.columns)
        self.assertIn('nodeName', processed.columns)
        
        # Check values
        self.assertEqual(processed['project_id'].iloc[0], 'test-project')
        self.assertEqual(processed['region'].iloc[0], 'us-central1')
        self.assertEqual(processed['nodeName'].iloc[0], 'test-node')
        
        conn.close()
    
    def test_process_schematized_sensors(self):
        """Test schematized sensor data processing"""
        conn = uploader.get_sqlite_connection(self.db_path)
        df = uploader.query_sensor_data(conn, 5, 0, self.test_config)
        
        # Test without sanitization
        processed = uploader.process_schematized_sensors(df, self.test_config, sanitize=False)
        
        # Check all expected fields are present
        expected_fields = [
            'project_id', 'region', 'nodeName', 'sync_time',
            'sensor_id', 'timestamp', 'temperature', 'humidity',
            'pressure', 'voltage', 'anomaly_flag', 'anomaly_type',
            'location', 'latitude', 'longitude'
        ]
        
        for field in expected_fields:
            self.assertIn(field, processed.columns)
        
        # Check location data is preserved
        self.assertEqual(processed['location'].iloc[0], 'Test Location')
        self.assertAlmostEqual(processed['latitude'].iloc[0], 41.8781, places=3)
        
        conn.close()
    
    def test_process_sanitized_sensors(self):
        """Test sanitized sensor data processing"""
        conn = uploader.get_sqlite_connection(self.db_path)
        df = uploader.query_sensor_data(conn, 5, 0, self.test_config)
        
        # Test with sanitization
        processed = uploader.process_schematized_sensors(df, self.test_config, sanitize=True)
        
        # Check location is redacted
        self.assertEqual(processed['location'].iloc[0], 'REDACTED')
        
        # Check GPS coordinates are rounded
        self.assertEqual(processed['latitude'].iloc[0], 41.9)  # Rounded to 1 decimal
        self.assertEqual(processed['longitude'].iloc[0], -87.6)  # Rounded to 1 decimal
        
        conn.close()
    
    def test_process_aggregated_sensors(self):
        """Test aggregated sensor data processing"""
        conn = uploader.get_sqlite_connection(self.db_path)
        df = uploader.query_sensor_data(conn, 20, 0, self.test_config)
        
        results = uploader.process_aggregated_sensors(df, self.test_config)
        
        # Check we have both aggregates and anomalies
        self.assertIn('aggregates', results)
        self.assertIn('anomalies', results)
        
        # Check aggregates
        aggregates = results['aggregates']
        self.assertGreater(len(aggregates), 0)
        self.assertIn('time_window', aggregates.columns)
        self.assertIn('avg_temperature', aggregates.columns)
        self.assertIn('anomaly_count', aggregates.columns)
        
        # Check anomalies (we inserted some)
        anomalies = results['anomalies']
        self.assertIsNotNone(anomalies)
        self.assertGreater(len(anomalies), 0)
        self.assertIn('anomaly_type', anomalies.columns)
        
        conn.close()
    
    def test_timestamp_tracking(self):
        """Test timestamp tracking functionality"""
        # Create a temporary directory for timestamp file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_config = self.test_config.copy()
            test_config['database']['path'] = os.path.join(tmpdir, 'test.db')
            
            # Test reading when no file exists
            timestamp = uploader.read_last_batch_timestamp(test_config)
            self.assertIsNone(timestamp)
            
            # Test writing timestamp
            test_timestamp = datetime.now(timezone.utc)
            uploader.write_last_batch_timestamp(test_timestamp, test_config)
            
            # Test reading back
            read_timestamp = uploader.read_last_batch_timestamp(test_config)
            self.assertIsNotNone(read_timestamp)
            self.assertEqual(
                test_timestamp.replace(microsecond=0),
                read_timestamp.replace(microsecond=0)
            )
    
    def test_get_max_timestamp_from_chunk(self):
        """Test extracting maximum timestamp from chunk"""
        conn = uploader.get_sqlite_connection(self.db_path)
        df = uploader.query_sensor_data(conn, 10, 0, self.test_config)
        
        # Process the data first
        processed = uploader.process_schematized_sensors(df, self.test_config)
        
        max_timestamp = uploader.get_max_timestamp_from_chunk(processed)
        self.assertIsNotNone(max_timestamp)
        
        # Should be the latest timestamp in the chunk
        expected_max = processed['timestamp'].max()
        self.assertEqual(max_timestamp, expected_max)
        
        conn.close()
    
    def test_empty_database(self):
        """Test handling of empty database"""
        # Create empty database
        empty_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        empty_path = empty_db.name
        empty_db.close()
        
        conn = sqlite3.connect(empty_path)
        conn.execute('''
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME,
                sensor_id TEXT,
                temperature REAL,
                synced BOOLEAN DEFAULT 0
            )
        ''')
        conn.close()
        
        # Test querying empty database
        test_config = self.test_config.copy()
        test_config['database']['path'] = empty_path
        
        conn = uploader.get_sqlite_connection(empty_path)
        df = uploader.query_sensor_data(conn, 10, 0, test_config)
        
        self.assertTrue(df.empty)
        conn.close()
        
        # Clean up
        os.unlink(empty_path)
    
    def test_database_not_found(self):
        """Test handling of missing database file"""
        with self.assertRaises(uploader.FatalError) as context:
            uploader.get_sqlite_connection('/path/to/nonexistent.db')
        
        self.assertIn('SQLite database not found', str(context.exception))


class TestConfigurationHandling(unittest.TestCase):
    """Test configuration loading and validation"""
    
    def test_load_config_with_env_overrides(self):
        """Test loading configuration with environment variable overrides"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('''
project_id: "original-project"
dataset: "original-dataset"
database:
  path: "/original/path.db"
metadata:
  region: "original-region"
''')
            config_path = f.name
        
        # Set environment variables
        os.environ['PROJECT_ID'] = 'env-project'
        os.environ['DATABASE_PATH'] = '/env/path.db'
        os.environ['REGION'] = 'env-region'
        
        try:
            config = uploader.load_config(config_path)
            
            # Check overrides
            self.assertEqual(config['project_id'], 'env-project')
            self.assertEqual(config['database']['path'], '/env/path.db')
            self.assertEqual(config['metadata']['region'], 'env-region')
            
        finally:
            # Clean up
            os.unlink(config_path)
            del os.environ['PROJECT_ID']
            del os.environ['DATABASE_PATH']
            del os.environ['REGION']


if __name__ == '__main__':
    unittest.main()