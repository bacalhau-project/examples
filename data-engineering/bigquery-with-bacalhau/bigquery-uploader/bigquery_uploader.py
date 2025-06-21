#!/usr/bin/env uv run -s
# /// script
# dependencies = [
#     "PyYAML",
#     "duckdb",
#     "pandas",
#     "google-cloud-bigquery",
#     "pyarrow",
#     "pandas-gbq",
# ]
# ///
"""
Unified Log Processor for BigQuery Upload
Configurable pipeline supporting: raw, schematized, sanitized, and aggregated processing

Dependencies:
- PyYAML for configuration file parsing
- DuckDB for log file processing
- pandas for data manipulation
- google-cloud-bigquery for BigQuery operations
- pyarrow for efficient BigQuery uploads
"""

import os
import sys
import yaml
import time
import json
import logging
import traceback
import functools
import ipaddress
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import duckdb
import pandas as pd
from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions

# Suppress pandas-gbq future warning
warnings.filterwarnings('ignore', message='Loading pandas DataFrame into BigQuery will require pandas-gbq package version', category=FutureWarning)


class FatalError(Exception):
    """Exception raised for fatal errors that should cause immediate program exit"""
    pass


def get_timestamp_file_path(config: Optional[Dict[str, Any]] = None) -> Path:
    """Get the path to the timestamp tracking file"""
    if config and config.get('input_paths'):
        # Get the first input path and use its directory
        first_input_path = config['input_paths'][0]
        # Handle glob patterns by taking the directory part
        if '*' in first_input_path or '?' in first_input_path:
            # Extract directory from glob pattern, handling ** patterns
            path_obj = Path(first_input_path)
            # Find the first part without wildcards
            parts = path_obj.parts
            clean_parts = []
            for part in parts:
                if '*' in part or '?' in part:
                    break
                clean_parts.append(part)
            if clean_parts:
                log_dir = Path(*clean_parts)
            else:
                # If pattern starts with wildcard, use current directory
                log_dir = Path('.')
        else:
            # Regular file path
            log_dir = Path(first_input_path).parent
        return log_dir / ".last_batch_timestamp.json"
    else:
        # Fallback to current behavior for backward compatibility
        script_dir = Path(__file__).parent
        return script_dir / ".last_batch_timestamp.json"


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
        'description': 'Tracks the latest log timestamp processed to prevent duplicate uploads'
    }

    try:
        with open(timestamp_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Updated last batch timestamp to: {timestamp.isoformat()}")

    except Exception as e:
        logger.error(f"Error writing timestamp file: {e}")
        raise


def format_timestamp_for_duckdb(timestamp: datetime) -> str:
    """Format timestamp for DuckDB Apache log comparison"""
    # Apache log format: [10/Oct/2000:13:55:36 -0700]
    # Convert timezone offset format from +00:00 to +0000
    formatted = timestamp.strftime('%d/%b/%Y:%H:%M:%S %z')
    # Remove colon from timezone offset only: +00:00 -> +0000, -05:00 -> -0500
    # The timezone offset is always at the end and has format +HH:MM or -HH:MM
    if len(formatted) >= 3 and formatted[-3] == ':':
        # Remove the colon from timezone: "+00:00" -> "+0000"
        formatted = formatted[:-3] + formatted[-2:]
    return f'[{formatted}]'


def get_max_timestamp_from_chunk(df: pd.DataFrame) -> Optional[datetime]:
    """Extract the maximum timestamp from a processed chunk"""
    if df.empty:
        return None

    # For raw mode, we don't have parsed timestamps
    if 'timestamp' not in df.columns:
        return None

    # Filter out null/invalid timestamps
    valid_timestamps = df['timestamp'].dropna()
    if valid_timestamps.empty:
        return None

    # Return the maximum timestamp
    max_timestamp = valid_timestamps.max()

    # Ensure it's timezone-aware
    if max_timestamp.tzinfo is None:
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
    "dataset": "log_analytics",
    "credentials_path": "/bacalhau_secret/gcp-creds.json",
    "input_paths": ["/bacalhau_data/*.log"],  # List of glob patterns for input files
    "tables": {
        "raw": "raw_logs",
        "schematized": "log_results",
        "sanitized": "log_results",
        "aggregated": "log_aggregates",
        "emergency": "emergency_logs"
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
        bigquery.SchemaField("raw_line", "STRING", mode="REQUIRED"),
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
        bigquery.SchemaField("ip", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("method", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("path", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("protocol", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("status", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("bytes", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("referer", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("user_agent", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("hostname", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("status_category", "STRING", mode="NULLABLE"),
    ],
    "aggregated": [
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("hostname", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("time_window", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("ok_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("client_error_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("not_found_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("system_error_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("total_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("total_bytes", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("avg_bytes", "FLOAT", mode="NULLABLE"),
    ],
    "emergency": [
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("nodeName", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("method", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("path", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("status", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("bytes", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("user_agent", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("referer", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("alert_level", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ip", "STRING", mode="NULLABLE"),
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
    """Load configuration from YAML file or use defaults

    Environment variable overrides (applied after loading YAML):
    - PROJECT_ID: Override project_id
    - DATASET: Override dataset
    - NODE_ID: Override node_id
    - REGION: Override metadata.region
    - PROVIDER: Override metadata.provider
    - HOSTNAME: Override metadata.hostname
    - GOOGLE_APPLICATION_CREDENTIALS: Override credentials_path
    - CREDENTIALS_FILE or CREDENTIALS_PATH: Override credentials_path
    - LOG_FILE or log_file: Override input_paths with single log file

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dict containing merged configuration with environment overrides
    """
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
                    'CREDENTIALS_PATH': 'credentials_path'
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

                # Special handling for log file environment variables (both cases)
                log_file_env = os.environ.get('LOG_FILE') or os.environ.get('log_file')
                if log_file_env:
                    config['input_paths'] = [log_file_env]
                    env_var_name = 'LOG_FILE' if os.environ.get('LOG_FILE') else 'log_file'
                    logger.info(f"Overriding input_paths with {env_var_name}: {log_file_env}")

                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise RuntimeError(f"Failed to load configuration from {config_path}: {e}")
    else:
        raise RuntimeError(f"Configuration file not found at {config_path}. Cannot proceed without configuration.")

def sanitize_ip(ip_str: str) -> str:
    """Sanitize IP address for privacy preservation"""
    if pd.isna(ip_str) or ip_str == '-':
        return '-'

    try:
        ip = ipaddress.ip_address(ip_str)
        if isinstance(ip, ipaddress.IPv4Address):
            # Zero out the last octet for IPv4
            return str(ipaddress.IPv4Address(int(ip) & 0xFFFFFF00))
        elif isinstance(ip, ipaddress.IPv6Address):
            # Zero out the last 64 bits for IPv6
            return str(ipaddress.IPv6Address(int(ip) & (0xFFFFFFFFFFFFFFFF << 64)))
        else:
            return ip_str
    except ValueError:
        # If it's not a valid IP, return as-is
        return ip_str

def categorize_status(status_code: int) -> str:
    """Categorize HTTP status codes"""
    if pd.isna(status_code):
        return 'Unknown'

    status_code = int(status_code)
    if 200 <= status_code < 300:
        return 'OK'
    elif 300 <= status_code < 400:
        return 'Redirect'
    elif status_code == 404:
        return 'Not Found'
    elif 400 <= status_code < 500:
        return 'Client Error'
    elif 500 <= status_code < 600:
        return 'SystemError'
    else:
        return 'Unknown'

def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse Apache log timestamp"""
    if pd.isna(timestamp_str) or timestamp_str == '-':
        return None

    try:
        # Apache log format: [10/Oct/2000:13:55:36 -0700]
        timestamp_str = timestamp_str.strip('[]')
        return datetime.strptime(timestamp_str, '%d/%b/%Y:%H:%M:%S %z')
    except (ValueError, TypeError):
        return None

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

def process_raw(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Process logs with minimal transformation"""
    result = pd.DataFrame()
    result['raw_line'] = df.apply(lambda row: ' '.join(row.astype(str)), axis=1)
    result['upload_time'] = datetime.now(timezone.utc)
    result['project_id'] = config['project_id']
    result['region'] = config['metadata']['region']
    result['nodeName'] = config['node_id']
    return result

def process_schematized(df: pd.DataFrame, config: Dict[str, Any], sanitize: bool = False) -> pd.DataFrame:
    """Process logs with full schema parsing"""
    # Parse the CSV columns
    result = pd.DataFrame()

    # Add metadata
    result['project_id'] = config['project_id']
    result['region'] = config['metadata']['region']
    result['nodeName'] = config['node_id']
    result['sync_time'] = datetime.now(timezone.utc)

    # Parse log fields
    result['ip'] = df['column0'].astype(str)
    if sanitize:
        result['ip'] = result['ip'].apply(sanitize_ip)

    result['user_id'] = df.get('column2', '-').astype(str)
    result['timestamp'] = df.get('column3', '').apply(parse_timestamp)

    # Parse HTTP request
    request_parts = df.get('column4', '').str.split(' ', expand=True)
    result['method'] = request_parts[0] if 0 in request_parts.columns else None
    result['path'] = request_parts[1] if 1 in request_parts.columns else None
    result['protocol'] = request_parts[2] if 2 in request_parts.columns else None

    # Parse status and bytes
    result['status'] = pd.to_numeric(df.get('column5', 0), errors='coerce').fillna(0).astype(int)
    result['bytes'] = pd.to_numeric(df.get('column6', 0), errors='coerce').fillna(0).astype(int)

    # Parse optional fields
    result['referer'] = df.get('column7', '-').astype(str)
    result['user_agent'] = df.get('column8', '-').astype(str)

    # Add provider metadata
    result['hostname'] = config['metadata']['hostname']
    result['provider'] = config['metadata']['provider']

    # Categorize status
    result['status_category'] = result['status'].apply(categorize_status)

    # Use categorical types for memory efficiency
    for col in ['method', 'protocol', 'status_category', 'provider', 'hostname']:
        if col in result.columns:
            result[col] = result[col].astype('category')

    return result

def process_aggregated(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Process logs with aggregation and emergency extraction"""
    # First, get the schematized data (without sanitization for emergency logs)
    parsed_df = process_schematized(df, config, sanitize=False)

    # Extract emergency events (status >= 500)
    emergency_mask = parsed_df['status'] >= 500
    emergency_logs = None

    if emergency_mask.any():
        emergency_logs = pd.DataFrame()
        emergency_logs['project_id'] = config['project_id']
        emergency_logs['region'] = config['metadata']['region']
        emergency_logs['nodeName'] = config['node_id']
        emergency_logs['timestamp'] = parsed_df.loc[emergency_mask, 'timestamp']
        emergency_logs['method'] = parsed_df.loc[emergency_mask, 'method']
        emergency_logs['path'] = parsed_df.loc[emergency_mask, 'path']
        emergency_logs['status'] = parsed_df.loc[emergency_mask, 'status']
        emergency_logs['bytes'] = parsed_df.loc[emergency_mask, 'bytes']
        emergency_logs['user_agent'] = parsed_df.loc[emergency_mask, 'user_agent']
        emergency_logs['referer'] = parsed_df.loc[emergency_mask, 'referer']
        emergency_logs['alert_level'] = "critical"
        emergency_logs['ip'] = parsed_df.loc[emergency_mask, 'ip']
        emergency_logs['sync_time'] = datetime.now(timezone.utc)

    # Create hourly aggregates
    parsed_df['time_window'] = pd.to_datetime(parsed_df['timestamp']).dt.floor('h')

    # Group by time window and calculate aggregates
    aggregates = parsed_df.groupby('time_window').agg({
        'status_category': lambda x: {
            'ok_count': (x == 'OK').sum(),
            'client_error_count': (x == 'Client Error').sum(),
            'not_found_count': (x == 'Not Found').sum(),
            'system_error_count': (x == 'SystemError').sum(),
            'total_count': len(x)
        },
        'bytes': ['sum', 'mean']
    }).reset_index()

    # Flatten the aggregated data
    result = pd.DataFrame()
    result['project_id'] = config['project_id']
    result['region'] = config['metadata']['region']
    result['nodeName'] = config['node_id']
    result['provider'] = config['metadata']['provider']
    result['hostname'] = config['metadata']['hostname']
    result['time_window'] = aggregates['time_window']

    # Extract status counts
    status_counts = pd.DataFrame(aggregates['status_category'].tolist())
    result['ok_count'] = status_counts['ok_count']
    result['client_error_count'] = status_counts['client_error_count']
    result['not_found_count'] = status_counts['not_found_count']
    result['system_error_count'] = status_counts['system_error_count']
    result['total_count'] = status_counts['total_count']

    # Add byte statistics
    result['total_bytes'] = aggregates[('bytes', 'sum')]
    result['avg_bytes'] = aggregates[('bytes', 'mean')]

    return {
        'aggregates': result,
        'emergency': emergency_logs
    }

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

def process_chunk(conn: duckdb.DuckDBPyConnection, chunk_num: int, chunk_size: int,
                  client: bigquery.Client, config: Dict[str, Any], input_patterns: List[str],
                  last_timestamp: Optional[datetime] = None) -> tuple[int, Optional[datetime]]:
    """Process a single chunk of data"""
    offset = chunk_num * chunk_size

    # Build file list from patterns
    file_list = []
    for pattern in input_patterns:
        file_list.append(f"'{pattern}'")
    files_str = ', '.join(file_list)

    # Build query with optional timestamp filtering
    base_query = f"SELECT * FROM read_csv_auto([{files_str}], delim=' ', header=false)"

    # Add timestamp filtering if we have a last timestamp
    if last_timestamp and config['pipeline_mode'] in ['schematized', 'sanitized', 'aggregated']:
        # For Apache logs, timestamp is in column3 (0-indexed column 3)
        # Format: [10/Oct/2000:13:55:36 -0700]
        timestamp_filter = format_timestamp_for_duckdb(last_timestamp)

        query = f"""
        WITH parsed_logs AS (
            {base_query}
        ),
        filtered_logs AS (
            SELECT * FROM parsed_logs
            WHERE column3 > '{timestamp_filter}'
        )
        SELECT * FROM filtered_logs
        LIMIT {chunk_size} OFFSET {offset}
        """

        logger.info(f"Filtering logs newer than: {last_timestamp.isoformat()} (Apache format: {timestamp_filter})")
    else:
        query = f"""
        {base_query}
        LIMIT {chunk_size} OFFSET {offset}
        """

    df = conn.execute(query).fetchdf()

    if df.empty:
        return 0

    rows_processed = len(df)
    pipeline_mode = config['pipeline_mode']
    chunk_max_timestamp = None

    try:
        if pipeline_mode == 'raw':
            processed = process_raw(df, config)
            table_name = config['tables']['raw']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            # Raw mode doesn't have parsed timestamps, so we can't track them

        elif pipeline_mode == 'schematized':
            processed = process_schematized(df, config, sanitize=False)
            table_name = config['tables']['schematized']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            chunk_max_timestamp = get_max_timestamp_from_chunk(processed)

        elif pipeline_mode == 'sanitized':
            processed = process_schematized(df, config, sanitize=True)
            table_name = config['tables']['sanitized']
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            upload_to_bigquery(client, table_id, processed, config=config)
            chunk_max_timestamp = get_max_timestamp_from_chunk(processed)

        elif pipeline_mode == 'aggregated':
            results = process_aggregated(df, config)

            # Upload aggregates
            if not results['aggregates'].empty:
                table_name = config['tables']['aggregated']
                table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
                upload_to_bigquery(client, table_id, results['aggregates'], config=config)

            # Upload emergency logs if any
            if results['emergency'] is not None and not results['emergency'].empty:
                table_name = config['tables']['emergency']
                table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
                upload_to_bigquery(client, table_id, results['emergency'], config=config)
                logger.warning(f"Found {len(results['emergency'])} emergency events in chunk {chunk_num}")
                chunk_max_timestamp = get_max_timestamp_from_chunk(results['emergency'])
            elif not results['aggregates'].empty:
                # For aggregated data, use the time_window field
                max_window = results['aggregates']['time_window'].max()
                if pd.notna(max_window):
                    chunk_max_timestamp = max_window.to_pydatetime()
                    if chunk_max_timestamp.tzinfo is None:
                        chunk_max_timestamp = chunk_max_timestamp.replace(tzinfo=timezone.utc)

    except Exception as e:
        logger.error(f"Error processing chunk {chunk_num}: {e}")
        logger.error(traceback.format_exc())
        # Continue processing other chunks

    finally:
        # Clean up memory
        if 'df' in locals():
            del df
        if 'processed' in locals():
            del processed
        if 'results' in locals():
            del results

    return rows_processed, chunk_max_timestamp

def run_pipeline(config: Dict[str, Any]):
    """Run the log processing pipeline based on configuration"""
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

    # Validate input paths exist
    input_paths = config.get('input_paths', [])
    if not input_paths:
        raise RuntimeError("ERROR: No input_paths specified in config or LOG_FILE environment variable")

    for path in input_paths:
        # Skip validation for glob patterns or if file might be created later
        if '*' not in path and '?' not in path and not os.path.exists(path):
            logger.warning(f"Input file not found: {path} (it may be created later)")

    # FAIL-FAST: Validate that files exist before initializing BigQuery client
    # This prevents wasting time on BigQuery connection if no files are available
    conn = duckdb.connect()
    input_patterns = config.get('input_paths', ['/bacalhau_data/*.log'])

    try:
        file_list = []
        for pattern in input_patterns:
            file_list.append(f"'{pattern}'")
        files_str = ', '.join(file_list)

        # Try to read just one row to validate files exist
        test_query = f"SELECT * FROM read_csv_auto([{files_str}], delim=' ', header=false) LIMIT 1"
        test_result = conn.execute(test_query).fetchdf()

        if test_result.empty:
            logger.warning("No data found in input files, but files may exist and be empty")
        else:
            logger.info(f"Successfully validated input files - found data to process")

    except Exception as e:
        error_msg = str(e)
        if "No files found that match the pattern" in error_msg:
            logger.error(f"FATAL: No log files found matching patterns: {input_patterns}")
            logger.error(f"Error: {error_msg}")
            logger.error("Cannot proceed with processing.")
            conn.close()
            raise FatalError(f"No log files found matching patterns: {input_patterns}. Cannot proceed with processing.")
        else:
            logger.error(f"FATAL: Error validating input files: {error_msg}")
            conn.close()
            raise FatalError(f"Failed to validate input files: {error_msg}")

    conn.close()

    # Initialize BigQuery client
    try:
        client = bigquery.Client(project=config['project_id'])
        logger.info(f"Successfully connected to BigQuery project: {config['project_id']}")
    except Exception as e:
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
        # Ensure both aggregated and emergency tables exist
        for table_type in ['aggregated', 'emergency']:
            table_name = config['tables'][table_type]
            table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"
            schema = SCHEMAS[table_type]
            ensure_table_exists(client, table_id, schema, config=config)

    # Read last batch timestamp
    last_batch_timestamp = read_last_batch_timestamp(config)

    # Process data in chunks
    conn = duckdb.connect()
    chunk_num = 0
    total_rows = 0
    failed_chunks = []
    max_processed_timestamp = last_batch_timestamp
    input_patterns = config.get('input_paths', ['/bacalhau_data/*.log'])

    while True:
        try:
            rows, chunk_timestamp = process_chunk(conn, chunk_num, config['chunk_size'], client, config, input_patterns, last_batch_timestamp)
            if rows == 0:
                break
            total_rows += rows

            # Track the maximum timestamp processed
            if chunk_timestamp and (max_processed_timestamp is None or chunk_timestamp > max_processed_timestamp):
                max_processed_timestamp = chunk_timestamp

            chunk_num += 1
        except Exception as e:
            error_msg = str(e)
            if "No files found that match the pattern" in error_msg:
                logger.error("FATAL: Log files disappeared during processing - this should not happen after validation")
                logger.error(f"Error: {error_msg}")
                conn.close()
                raise FatalError(f"Log files disappeared during processing: {error_msg}")
            else:
                logger.error(f"Failed to process chunk {chunk_num}: {e}")
                failed_chunks.append(chunk_num)
                chunk_num += 1
                # Continue with next chunk for non-file-related errors

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
    if failed_chunks:
        logger.warning(f"Failed chunks: {failed_chunks}")

    if last_batch_timestamp:
        logger.info(f"Processed logs newer than: {last_batch_timestamp.isoformat()}")
    else:
        logger.info("Processed all available logs (first run)")

    if max_processed_timestamp:
        logger.info(f"Latest log timestamp processed: {max_processed_timestamp.isoformat()}")

def main():
    """Main entry point with configuration watching

    Environment Variables:
    - CONFIG_FILE: Required. Path to the YAML configuration file
    - LOG_FILE or log_file: Optional. Override input_paths from config with a single log file path
    - CREDENTIALS_FILE or CREDENTIALS_PATH: Optional. Path to BigQuery service account credentials
    - PROJECT_ID: Optional. Override project_id from config
    - DATASET: Optional. Override dataset from config
    - NODE_ID: Optional. Override node_id from config
    - REGION: Optional. Override metadata.region from config
    - PROVIDER: Optional. Override metadata.provider from config
    - HOSTNAME: Optional. Override metadata.hostname from config
    """
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
        logger.info(f"Input paths: {initial_config.get('input_paths', ['/bacalhau_data/*.log'])}")
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
