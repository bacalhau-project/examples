#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pandas>=2.2.3",
#     "pydantic>=2.0.0",
# ]
# ///
"""Test full upload cycle with each pipeline type"""

import sqlite3
import pandas as pd
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil
from pipeline_manager import PipelineManager, PipelineType

def create_test_database(db_path: str) -> None:
    """Create a test SQLite database with sensor data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create sensor_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sensor_id TEXT NOT NULL,
            location TEXT,
            temperature REAL,
            humidity REAL,
            latitude REAL,
            longitude REAL,
            status_code INTEGER,
            anomaly_flag INTEGER DEFAULT 0,
            reading_value REAL
        )
    """)
    
    # Insert test data
    base_time = datetime.now() - timedelta(hours=2)
    
    test_data = []
    for i in range(20):
        timestamp = base_time + timedelta(minutes=i*5)
        anomaly = 1 if i % 5 == 0 else 0  # Every 5th record is an anomaly
        
        test_data.append({
            'timestamp': timestamp.isoformat(),
            'sensor_id': f'sensor_{i % 3}',
            'location': f'location_{i % 2}',
            'temperature': 20.0 + (i % 10),
            'humidity': 50.0 + (i % 20),
            'latitude': 37.7749 + (i % 100) * 0.0001,
            'longitude': -122.4194 + (i % 100) * 0.0001,
            'status_code': 200,
            'anomaly_flag': anomaly,
            'reading_value': 100.0 + i
        })
    
    df = pd.DataFrame(test_data)
    df.to_sql('sensor_logs', conn, if_exists='append', index=False)
    
    conn.commit()
    conn.close()
    print(f"✓ Created test database with {len(test_data)} records")

def test_pipeline_type(db_path: str, pipeline_type: str) -> dict:
    """Test a specific pipeline type."""
    print(f"\n[Testing {pipeline_type} pipeline]")
    
    # Initialize pipeline manager
    pm = PipelineManager(db_path)
    
    # Set pipeline type (convert string to enum)
    pipeline_enum = PipelineType(pipeline_type)
    pm.set_pipeline(pipeline_enum, updated_by='test_script')
    current = pm.get_current_pipeline()
    print(f"✓ Set pipeline type to: {current}")
    
    # Start execution (using current pipeline type)
    exec_id = pm.start_execution()
    print(f"✓ Started execution: {exec_id}")
    
    # Simulate data processing based on pipeline type
    conn = sqlite3.connect(db_path)
    
    if pipeline_type == 'raw':
        # Raw pipeline: all data
        df = pd.read_sql_query("SELECT * FROM sensor_logs", conn)
        print(f"  Raw pipeline: Processing {len(df)} records")
        
    elif pipeline_type == 'schematized':
        # Schematized: structured data
        df = pd.read_sql_query("SELECT * FROM sensor_logs", conn)
        print(f"  Schematized pipeline: Processing {len(df)} structured records")
        
    elif pipeline_type == 'filtered':
        # Filtered: apply some filtering logic
        df = pd.read_sql_query(
            "SELECT * FROM sensor_logs WHERE temperature > 25", 
            conn
        )
        print(f"  Filtered pipeline: Processing {len(df)} filtered records")
        
    elif pipeline_type == 'emergency':
        # Emergency: only anomalies
        df = pd.read_sql_query(
            "SELECT * FROM sensor_logs WHERE anomaly_flag = 1", 
            conn
        )
        print(f"  Emergency pipeline: Processing {len(df)} anomaly records")
    
    conn.close()
    
    # Complete execution
    pm.complete_execution(exec_id, records_processed=len(df))
    print(f"✓ Completed execution with {len(df)} records")
    
    # Get execution history
    history = pm.get_execution_history(limit=1)
    if history:
        latest = history[0]
        print(f"✓ Execution recorded: {latest.completed_at} - {latest.records_processed} records")
    
    return {
        'pipeline_type': pipeline_type,
        'records_processed': len(df),
        'execution_id': exec_id
    }

def test_pipeline_switching(db_path: str) -> None:
    """Test pipeline type changes between cycles."""
    print("\n[Testing Pipeline Switching]")
    
    pm = PipelineManager(db_path)
    
    # Test switching between types
    pipeline_sequence = ['raw', 'filtered', 'emergency', 'schematized']
    
    for i, pipeline_type in enumerate(pipeline_sequence):
        pipeline_enum = PipelineType(pipeline_type)
        pm.set_pipeline(pipeline_enum, updated_by=f'switch_test_{i}')
        current = pm.get_current_pipeline()
        print(f"✓ Switched to {current} pipeline")
        
        # Verify it persists
        pm2 = PipelineManager(db_path)
        verified = pm2.get_current_pipeline()
        assert verified.pipeline_type.value == pipeline_type, f"Pipeline type mismatch: {verified.pipeline_type.value} != {pipeline_type}"
    
    print("✓ All pipeline switches successful")

def test_table_routing(pipeline_type: str) -> str:
    """Test table routing based on pipeline type."""
    table_suffix_map = {
        "raw": "0_raw",
        "schematized": "1_schematized", 
        "filtered": "2_filtered",
        "emergency": "4_emergency",
    }
    
    base_table = "sensor_readings"
    suffix = table_suffix_map.get(pipeline_type, "0_raw")
    routed_table = f"{base_table}_{suffix}"
    
    print(f"  Pipeline '{pipeline_type}' routes to table: {routed_table}")
    return routed_table

def main():
    """Run all pipeline tests."""
    print("Pipeline Upload Cycle Tests")
    print("=" * 50)
    
    # Create temporary test database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_pipeline.db')
        
        # Create test data
        create_test_database(db_path)
        
        # Test each pipeline type
        results = []
        for pipeline_type in ['raw', 'schematized', 'filtered', 'emergency']:
            result = test_pipeline_type(db_path, pipeline_type)
            
            # Test table routing
            routed_table = test_table_routing(pipeline_type)
            result['routed_table'] = routed_table
            
            results.append(result)
        
        # Test pipeline switching
        test_pipeline_switching(db_path)
        
        # Display summary
        print("\n" + "=" * 50)
        print("Test Summary")
        print("=" * 50)
        
        for result in results:
            print(f"\n{result['pipeline_type'].upper()} Pipeline:")
            print(f"  - Records processed: {result['records_processed']}")
            print(f"  - Routed to table: {result['routed_table']}")
            print(f"  - Execution ID: {result['execution_id']}")
        
        # Check execution history
        pm = PipelineManager(db_path)
        history = pm.get_execution_history(limit=10)
        
        print(f"\nTotal executions recorded: {len(history)}")
        print("\nAll tests passed! ✓")

if __name__ == "__main__":
    main()