#!/usr/bin/env uv run -s
# /// script
# dependencies = [
#     "PyYAML",
#     "pandas",
#     "google-cloud-bigquery",
#     "pyarrow",
#     "pandas-gbq",
# ]
# ///
"""
Unified Sensor Data Processor for BigQuery Upload from SQLite Database
Configurable pipeline supporting: raw, schematized, sanitized, and aggregated processing

Dependencies:
- PyYAML for configuration file parsing
- pandas for data manipulation
- google-cloud-bigquery for BigQuery operations
- pyarrow for efficient BigQuery uploads
- sqlite3 (built-in) for database access
"""

import os
import sys
import yaml
import time
import json
import logging
import traceback
import functools
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions

# Suppress pandas-gbq future warning
warnings.filterwarnings('ignore', message='Loading pandas DataFrame into BigQuery will require pandas-gbq package version', category=FutureWarning)


class FatalError(Exception):
    """Exception raised for fatal errors that should cause immediate program exit"""
    pass


def get_sqlite_connection(db_path: str) -> sqlite3.Connection:
    """Create SQLite connection with optimized settings for container environments"""
    if not os.path.exists(db_path):
        raise FatalError(f"SQLite database not found: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    
    # Optimize for better concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB
    
    return conn


def get_timestamp_file_path(config: Optional[Dict[str, Any]] = None) -> Path:
    """Get the path to the timestamp tracking file"""
    if config and config.get('database', {}).get('path'):
        # Use the same directory as the database
        db_path = Path(config['database']['path'])
        return db_path.parent / ".last_batch_timestamp.json"
    else:
        # Fallback to current directory
        return Path('.') / ".last_batch_timestamp.json"


def read_last_batch_timestamp(config: Optional[Dict[str, Any]] = None) -> Optional[datetime]:
    """Read the last batch timestamp from the tracking file"""
    timestamp_file = get_timestamp_file_path(config)

    if not timestamp_file.exists():
        logger.info("No previous batch timestamp found - this appears to be the first run")
        return None

    try:
        with open(timestamp_file, 'r') as f:
            data = json.load(f)

        timestamp_str = data.get('last_batch_timestamp')
        if timestamp_str:
            # Parse ISO format timestamp
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            logger.warning("Invalid timestamp format in tracking file")
            return None

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Error reading timestamp file: {e}")
        return None


def write_last_batch_timestamp(timestamp: datetime, config: Optional[Dict[str, Any]] = None):
    """Write the last batch timestamp to the tracking file"""
    timestamp_file = get_timestamp_file_path(config)

    data = {
        'last_batch_timestamp': timestamp.isoformat(),
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'description': 'Tracks the latest sensor reading timestamp processed to prevent duplicate uploads'
    }

    try:
        with open(timestamp_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Updated last batch timestamp to: {timestamp.isoformat()}")

    except Exception as e:
        logger.error(f"Error writing timestamp file: {e}")
        raise


def get_max_timestamp_from_chunk(df: pd.DataFrame) -> Optional[datetime]:
    """Extract the maximum timestamp from a processed chunk"""
    if df.empty:
        return None

    # For raw mode, we should still have timestamps
    if 'timestamp' not in df.columns:
        return None

    # Filter out null/invalid timestamps
    valid_timestamps = df['timestamp'].dropna()
    if valid_timestamps.empty:
        return None

    # Return the maximum timestamp
    max_timestamp = valid_timestamps.max()

    # Ensure it's timezone-aware
    if hasattr(max_timestamp, 'tzinfo') and max_timestamp.tzinfo is None:
        max_timestamp = max_timestamp.replace(tzinfo=timezone.utc)

    return max_timestamp


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "pipeline_mode": "raw",  # Options: raw, schematized, sanitized, aggregated
    "chunk_size": 10000,
    "max_retries": 20,
    "base_retry_delay": 1,
    "max_retry_delay": 60,
    "check_interval": 30,  # How often to check for config changes (seconds)
    "project_id": "",
    "dataset": "sensor_analytics",
    "credentials_path": "/bacalhau_secret/gcp-creds.json",
    "database": {
        "path": "/bacalhau_data/sensor_data.db",
        "table": "sensor_readings",
        "sync_enabled": True  # Whether to update the synced flag
    },
    "tables": {
        "raw": "raw_sensor_data",
        "schematized": "sensor_readings",
        "sanitized": "sensor_readings_sanitized",
        "aggregated": "sensor_aggregates",
        "anomalies": "sensor_anomalies"
    },
    "node_id": "bacalhau-node",
    "metadata": {
        "region": "us-central1",
        "provider": "gcp",
        "hostname": "bacalhau-cluster"
    }
}

# BigQuery schemas for different pipeline modes
SCHEMAS = {
    "raw": [
        bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("sensor_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("vibration", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("voltage", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("status_code", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("anomaly_flag", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("anomaly_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("upload_time", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
    ],
    "schematized": [
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sync_time", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("sensor_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("vibration", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("voltage", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("status_code", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("anomaly_flag", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("anomaly_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("firmware_version", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("model", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("manufacturer", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("serial_number", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("location", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("latitude", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("longitude", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("deployment_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("installation_date", "STRING", mode="NULLABLE"),
    ],
    "aggregated": [
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("time_window", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("sensor_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("location", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("avg_temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("min_temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("max_temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("avg_humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("min_humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("max_humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("avg_pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("min_pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("max_pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("avg_voltage", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("anomaly_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("reading_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("sync_time", "TIMESTAMP", mode="REQUIRED"),
    ],
    "anomalies": [
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sensor_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("anomaly_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("temperature", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("humidity", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("pressure", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("voltage", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("location", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("firmware_version", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("model", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sync_time", "TIMESTAMP", mode="REQUIRED"),
    ]
}

def with_retries(func):
    """Decorator to add retry logic with exponential backoff"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        config = kwargs.get('config', DEFAULT_CONFIG)
        max_retries = config.get('max_retries', 20)
        base_delay = config.get('base_retry_delay', 1)
        max_delay = config.get('max_retry_delay', 60)

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    raise

                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)

    return wrapper

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file or use defaults"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                config = DEFAULT_CONFIG.copy()

                # Deep merge configuration
                def deep_merge(base, updates):
                    for key, value in updates.items():
                        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                            deep_merge(base[key], value)
                        else:
                            base[key] = value

                deep_merge(config, user_config)

                # Override with environment variables if they exist
                env_overrides = {
                    'PROJECT_ID': 'project_id',
                    'DATASET': 'dataset',
                    'NODE_ID': 'node_id',
                    'REGION': ('metadata', 'region'),
                    'PROVIDER': ('metadata', 'provider'),
                    'HOSTNAME': ('metadata', 'hostname'),
                    'GOOGLE_APPLICATION_CREDENTIALS': 'credentials_path',
                    'CREDENTIALS_FILE': 'credentials_path',
                    'CREDENTIALS_PATH': 'credentials_path',
                    'DATABASE_PATH': ('database', 'path'),
                    'DATABASE_FILE': ('database', 'path')
                }

                for env_var, config_key in env_overrides.items():
                    if os.environ.get(env_var):
                        if isinstance(config_key, tuple):
                            # Nested configuration
                            obj = config
                            for k in config_key[:-1]:
                                obj = obj[k]
                            obj[config_key[-1]] = os.environ[env_var]
                        else:
                            config[config_key] = os.environ[env_var]

                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise RuntimeError(f"Failed to load configuration from {config_path}: {e}")
    else:
        raise RuntimeError(f"Configuration file not found at {config_path}. Cannot proceed without configuration.")

def query_sensor_data(conn: sqlite3.Connection, chunk_size: int, offset: int, 
                     config: Dict[str, Any], last_timestamp: Optional[datetime] = None) -> pd.DataFrame:
    """Query sensor data from SQLite with optional timestamp filtering"""
    table_name = config.get('database', {}).get('table', 'sensor_readings')
    
    base_query = f"""
        SELECT * FROM {table_name}
        WHERE 1=1
    """
    
    # Add synced filter if sync is enabled
    if config.get('database', {}).get('sync_enabled', True):
        base_query += " AND synced = 0"
    
    # Add timestamp filter if provided
    if last_timestamp:
        base_query += f" AND timestamp > '{last_timestamp.isoformat()}'"
    
    query = f"{base_query} ORDER BY timestamp LIMIT {chunk_size} OFFSET {offset}"
    
    try:
        df = pd.read_sql_query(query, conn)
        # Convert timestamp strings to datetime objects
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        logger.error(f"Error querying sensor data: {e}")
        raise

def mark_as_synced(conn: sqlite3.Connection, ids: List[int], config: Dict[str, Any]):
    """Mark sensor readings as synced after successful upload"""
    if not config.get('database', {}).get('sync_enabled', True):
        return
    
    if not ids:
        return
    
    table_name = config.get('database', {}).get('table', 'sensor_readings')
    placeholders = ','.join('?' * len(ids))
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table_name} SET synced = 1 WHERE id IN ({placeholders})", ids)
        conn.commit()
        logger.info(f"Marked {len(ids)} records as synced")
    except Exception as e:
        logger.error(f"Error marking records as synced: {e}")
        conn.rollback()
        raise

def sanitize_location_data(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitize location data for privacy preservation"""
    result = df.copy()
    
    # Round GPS coordinates to city-level precision (1 decimal place)
    if 'latitude' in result.columns:
        result['latitude'] = result['latitude'].round(1)
    if 'longitude' in result.columns:
        result['longitude'] = result['longitude'].round(1)
    
    # Redact specific location names
    if 'location' in result.columns:
        result['location'] = 'REDACTED'
    
    return result

def process_raw_sensors(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Process sensor readings with minimal transformation"""
    result = df.copy()
    result['upload_time'] = datetime.now(timezone.utc)
    result['project_id'] = config['project_id']
    result['region'] = config['metadata']['region']
    result['nodeName'] = config['node_id']
    return result

def process_schematized_sensors(df: pd.DataFrame, config: Dict[str, Any], sanitize: bool = False) -> pd.DataFrame:
    """Process sensor readings with full schema"""
    result = pd.DataFrame()
    
    # Add metadata
    result['project_id'] = config['project_id']
    result['region'] = config['metadata']['region']
    result['nodeName'] = config['node_id']
    result['sync_time'] = datetime.now(timezone.utc)
    
    # Core sensor data
    result['sensor_id'] = df['sensor_id']
    result['timestamp'] = pd.to_datetime(df['timestamp'])
    result['temperature'] = df['temperature']
    result['humidity'] = df['humidity']
    result['pressure'] = df['pressure']
    result['vibration'] = df.get('vibration', 0.0)
    result['voltage'] = df['voltage']
    
    # Status and anomaly data
    result['status_code'] = df.get('status_code', 0)
    result['anomaly_flag'] = df.get('anomaly_flag', False)
    result['anomaly_type'] = df.get('anomaly_type', None)
    
    # Device metadata
    result['firmware_version'] = df.get('firmware_version', '')
    result['model'] = df.get('model', '')
    result['manufacturer'] = df.get('manufacturer', '')
    result['serial_number'] = df.get('serial_number', '')
    
    # Location data
    if sanitize:
        location_df = sanitize_location_data(df)
        result['location'] = location_df.get('location', 'UNKNOWN')
        result['latitude'] = location_df.get('latitude', 0.0)
        result['longitude'] = location_df.get('longitude', 0.0)
    else:
        result['location'] = df.get('location', 'UNKNOWN')
        result['latitude'] = df.get('latitude', 0.0)
        result['longitude'] = df.get('longitude', 0.0)
    
    # Deployment data
    result['deployment_type'] = df.get('deployment_type', '')
    result['installation_date'] = df.get('installation_date', '')
    
    # Use categorical types for memory efficiency
    for col in ['anomaly_type', 'model', 'manufacturer', 'deployment_type']:
        if col in result.columns:
            result[col] = result[col].astype('category')
    
    return result

def process_aggregated_sensors(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Process sensor readings with aggregation and anomaly extraction"""
    # First, get the schematized data
    parsed_df = process_schematized_sensors(df, config, sanitize=False)
    
    # Extract anomalies
    anomaly_mask = parsed_df['anomaly_flag'] == True
    anomalies_df = None
    
    if anomaly_mask.any():
        anomalies_df = pd.DataFrame()
        anomalies_df['project_id'] = config['project_id']
        anomalies_df['region'] = config['metadata']['region']
        anomalies_df['nodeName'] = config['node_id']
        anomalies_df['sensor_id'] = parsed_df.loc[anomaly_mask, 'sensor_id']
        anomalies_df['timestamp'] = parsed_df.loc[anomaly_mask, 'timestamp']
        anomalies_df['anomaly_type'] = parsed_df.loc[anomaly_mask, 'anomaly_type']
        anomalies_df['temperature'] = parsed_df.loc[anomaly_mask, 'temperature']
        anomalies_df['humidity'] = parsed_df.loc[anomaly_mask, 'humidity']
        anomalies_df['pressure'] = parsed_df.loc[anomaly_mask, 'pressure']
        anomalies_df['voltage'] = parsed_df.loc[anomaly_mask, 'voltage']
        anomalies_df['location'] = parsed_df.loc[anomaly_mask, 'location']
        anomalies_df['firmware_version'] = parsed_df.loc[anomaly_mask, 'firmware_version']
        anomalies_df['model'] = parsed_df.loc[anomaly_mask, 'model']
        anomalies_df['sync_time'] = datetime.now(timezone.utc)
    
    # Create hourly aggregates
    parsed_df['time_window'] = parsed_df['timestamp'].dt.floor('h')
    
    # Group by time window and sensor
    aggregates = parsed_df.groupby(['time_window', 'sensor_id', 'location']).agg({
        'temperature': ['mean', 'min', 'max'],
        'humidity': ['mean', 'min', 'max'],
        'pressure': ['mean', 'min', 'max'],
        'voltage': ['mean'],
        'anomaly_flag': 'sum',
        'timestamp': 'count'
    }).reset_index()
    
    # Flatten column names
    aggregates.columns = [
        'time_window', 'sensor_id', 'location',
        'avg_temperature', 'min_temperature', 'max_temperature',
        'avg_humidity', 'min_humidity', 'max_humidity',
        'avg_pressure', 'min_pressure', 'max_pressure',
        'avg_voltage', 'anomaly_count', 'reading_count'
    ]
    
    # Add metadata
    aggregates['project_id'] = config['project_id']
    aggregates['region'] = config['metadata']['region']
    aggregates['nodeName'] = config['node_id']
    aggregates['sync_time'] = datetime.now(timezone.utc)
    
    return {
        'aggregates': aggregates,
        'anomalies': anomalies_df
    }

@with_retries
def ensure_table_exists(client: bigquery.Client, table_id: str, schema: List[bigquery.SchemaField], config: Dict[str, Any] = None):
    """Ensure BigQuery table exists with correct schema"""
    try:
        client.get_table(table_id)
        logger.info(f"Table {table_id} already exists")
    except Exception:
        logger.info(f"Creating table {table_id}")
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table)

@with_retries
def upload_to_bigquery(client: bigquery.Client, table_id: str, data: pd.DataFrame, config: Dict[str, Any] = None):
    """Upload data to BigQuery with retry logic"""
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        autodetect=False,
    )

    job = client.load_table_from_dataframe(data, table_id, job_config=job_config)
    job.result()
    logger.info(f"Uploaded {len(data)} rows to {table_id}")

def process_chunk(conn: sqlite3.Connection, chunk_num: int, chunk_size: int,
                  client: bigquery.Client, config: Dict[str, Any],
                  last_timestamp: Optional[datetime] = None) -> Tuple[int, Optional[datetime], List[int]]:
    """Process a single chunk of sensor data"""
    offset = chunk_num * chunk_size
    
    # Query sensor data from SQLite
    df = query_sensor_data(conn, chunk_size, offset, config, last_timestamp)
    
    if df.empty:
        return 0, None, []
    
    rows_processed = len(df)
    pipeline_mode = config['pipeline_mode']
    chunk_max_timestamp = None
    record_ids = df['id'].tolist() if 'id' in df.columns else []
    
    try:
        if pipeline_mode == 'raw':
            processed = process_raw_sensors(df, config)
            table_name = config['tables']['raw']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            chunk_max_timestamp = get_max_timestamp_from_chunk(processed)
            
        elif pipeline_mode == 'schematized':
            processed = process_schematized_sensors(df, config, sanitize=False)
            table_name = config['tables']['schematized']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            chunk_max_timestamp = get_max_timestamp_from_chunk(processed)
            
        elif pipeline_mode == 'sanitized':
            processed = process_schematized_sensors(df, config, sanitize=True)
            table_name = config['tables']['sanitized']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            chunk_max_timestamp = get_max_timestamp_from_chunk(processed)
            
        elif pipeline_mode == 'aggregated':
            results = process_aggregated_sensors(df, config)
            
            # Upload aggregates
            if not results['aggregates'].empty:
                table_name = config['tables']['aggregated']
                table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
                upload_to_bigquery(client, table_id, results['aggregates'], config=config)
            
            # Upload anomalies if any
            if results['anomalies'] is not None and not results['anomalies'].empty:
                table_name = config['tables']['anomalies']
                table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
                upload_to_bigquery(client, table_id, results['anomalies'], config=config)
                logger.warning(f"Found {len(results['anomalies'])} anomalies in chunk {chunk_num}")
            
            # Get max timestamp from aggregates
            if not results['aggregates'].empty:
                max_window = results['aggregates']['time_window'].max()
                if pd.notna(max_window):
                    chunk_max_timestamp = max_window.to_pydatetime()
                    if chunk_max_timestamp.tzinfo is None:
                        chunk_max_timestamp = chunk_max_timestamp.replace(tzinfo=timezone.utc)
    
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_num}: {e}")
        logger.error(traceback.format_exc())
        # Don't mark as synced if upload failed
        record_ids = []
    
    finally:
        # Clean up memory
        if 'df' in locals():
            del df
        if 'processed' in locals():
            del processed
        if 'results' in locals():
            del results
    
    return rows_processed, chunk_max_timestamp, record_ids

def run_pipeline(config: Dict[str, Any]):
    """Run the sensor data processing pipeline based on configuration"""
    logger.info(f"Starting pipeline in {config['pipeline_mode']} mode")
    
    # Validate required configuration
    if not config.get('project_id'):
        raise RuntimeError("ERROR: project_id is required but not set in config or PROJECT_ID environment variable")
    
    # Set credentials path if specified and validate it exists
    credentials_path = config.get('credentials_path')
    if credentials_path:
        if not os.path.exists(credentials_path):
            raise RuntimeError(f"ERROR: Credentials file not found: {credentials_path}\n"
                             f"Check your config file or set CREDENTIALS_FILE/CREDENTIALS_PATH environment variable")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        logger.info(f"Using credentials from: {credentials_path}")
    else:
        logger.warning("No credentials_path specified - using default Google Cloud authentication")
    
    # Validate database path
    db_path = config.get('database', {}).get('path')
    if not db_path:
        raise RuntimeError("ERROR: No database path specified in config or DATABASE_PATH environment variable")
    
    # Initialize SQLite connection
    try:
        conn = get_sqlite_connection(db_path)
        logger.info(f"Successfully connected to SQLite database: {db_path}")
        
        # Verify table exists and has data
        table_name = config.get('database', {}).get('table', 'sensor_readings')
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE synced = 0")
        unsynced_count = cursor.fetchone()[0]
        logger.info(f"Found {unsynced_count} unsynced records in {table_name}")
        
        if unsynced_count == 0:
            logger.info("No unsynced records to process")
            conn.close()
            return
            
    except Exception as e:
        raise FatalError(f"Failed to connect to SQLite database: {e}")
    
    # Initialize BigQuery client
    try:
        client = bigquery.Client(project=config['project_id'])
        logger.info(f"Successfully connected to BigQuery project: {config['project_id']}")
    except Exception as e:
        conn.close()
        raise RuntimeError(f"ERROR: Failed to initialize BigQuery client: {e}\n"
                         f"Check your credentials and project_id configuration")
    
    # Ensure tables exist
    pipeline_mode = config['pipeline_mode']
    if pipeline_mode in ['raw', 'schematized', 'sanitized']:
        table_name = config['tables'][pipeline_mode]
        table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
        schema = SCHEMAS[pipeline_mode]
        ensure_table_exists(client, table_id, schema, config=config)
    elif pipeline_mode == 'aggregated':
        # Ensure both aggregated and anomalies tables exist
        for table_type in ['aggregated', 'anomalies']:
            table_name = config['tables'][table_type]
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            schema = SCHEMAS[table_type]
            ensure_table_exists(client, table_id, schema, config=config)
    
    # Read last batch timestamp
    last_batch_timestamp = read_last_batch_timestamp(config)
    
    # Process data in chunks
    chunk_num = 0
    total_rows = 0
    total_synced = 0
    failed_chunks = []
    max_processed_timestamp = last_batch_timestamp
    
    while True:
        try:
            rows, chunk_timestamp, record_ids = process_chunk(
                conn, chunk_num, config['chunk_size'], client, config, last_batch_timestamp
            )
            
            if rows == 0:
                break
            
            total_rows += rows
            
            # Mark records as synced if successful
            if record_ids and config.get('database', {}).get('sync_enabled', True):
                mark_as_synced(conn, record_ids, config)
                total_synced += len(record_ids)
            
            # Track the maximum timestamp processed
            if chunk_timestamp and (max_processed_timestamp is None or chunk_timestamp > max_processed_timestamp):
                max_processed_timestamp = chunk_timestamp
            
            chunk_num += 1
            
        except Exception as e:
            logger.error(f"Failed to process chunk {chunk_num}: {e}")
            failed_chunks.append(chunk_num)
            chunk_num += 1
            # Continue with next chunk
    
    conn.close()
    
    # Update the timestamp tracking file with the latest processed timestamp
    if max_processed_timestamp and max_processed_timestamp != last_batch_timestamp:
        try:
            write_last_batch_timestamp(max_processed_timestamp, config)
            logger.info(f"Updated batch timestamp tracking to: {max_processed_timestamp.isoformat()}")
        except Exception as e:
            logger.error(f"Failed to update timestamp tracking: {e}")
            # Don't fail the entire pipeline for timestamp tracking issues
    
    logger.info(f"Pipeline completed. Mode: {pipeline_mode}")
    logger.info(f"Total rows processed: {total_rows}")
    logger.info(f"Total records marked as synced: {total_synced}")
    if failed_chunks:
        logger.warning(f"Failed chunks: {failed_chunks}")
    
    if last_batch_timestamp:
        logger.info(f"Processed readings newer than: {last_batch_timestamp.isoformat()}")
    else:
        logger.info("Processed all available readings (first run)")
    
    if max_processed_timestamp:
        logger.info(f"Latest reading timestamp processed: {max_processed_timestamp.isoformat()}")

def main():
    """Main entry point with configuration watching"""
    # Check for required CONFIG_FILE environment variable
    config_file = os.environ.get('CONFIG_FILE')
    if not config_file:
        logger.error("ERROR: CONFIG_FILE environment variable is required but not set")
        sys.exit(1)
    
    # Check if the config file exists
    if not os.path.exists(config_file):
        logger.error(f"ERROR: Configuration file '{config_file}' does not exist")
        sys.exit(1)
    
    config_path = config_file
    
    # Load initial configuration - fail if not present
    try:
        initial_config = load_config(config_path)
        logger.info(f"Loaded configuration from {config_path}")
        logger.info(f"Pipeline mode: {initial_config['pipeline_mode']}")
        logger.info(f"Project ID: {initial_config['project_id']}")
        logger.info(f"Database path: {initial_config.get('database', {}).get('path')}")
    except Exception as e:
        logger.error(f"Failed to load initial configuration: {e}")
        sys.exit(1)
    
    last_config = None
    last_modified = 0
    
    while True:
        try:
            # Check if config file has been modified
            current_modified = os.path.getmtime(config_path)
            if current_modified > last_modified:
                new_config = load_config(config_path)
                
                # Run pipeline if config changed or first run
                if new_config != last_config:
                    logger.info("Configuration changed, running pipeline...")
                    run_pipeline(new_config)
                    last_config = new_config
                    last_modified = current_modified
                else:
                    logger.debug("Configuration unchanged, skipping run")
            
            # Wait before checking again
            check_interval = last_config.get('check_interval', 30) if last_config else 30
            logger.info(f"Waiting {check_interval} seconds before next check...")
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except FatalError as e:
            logger.error(f"Fatal error encountered: {e}")
            logger.error("Exiting immediately - this error cannot be recovered from.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            time.sleep(30)  # Wait before retrying

if __name__ == '__main__':
    main()