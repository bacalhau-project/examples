#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "tabulate>=0.9.0",
#     "boto3>=1.28.0",
# ]
# ///

"""Query summary of all data in S3 buckets and Unity Catalog tables."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from databricks import sql
from tabulate import tabulate
import boto3
from datetime import datetime

# Load environment variables
load_dotenv()

def query_unity_catalog():
    """Query all tables in Unity Catalog and show summary."""
    
    # Get Databricks credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    
    # Try to get warehouse ID from either DATABRICKS_WAREHOUSE_ID or extract from HTTP_PATH
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
        if "/warehouses/" in http_path:
            warehouse_id = http_path.split("/warehouses/")[-1]
    
    catalog = os.getenv("DATABRICKS_CATALOG", "expanso_databricks_workspace")
    # IMPORTANT: Use sensor_readings schema, not sensor_data
    schema = os.getenv("DATABRICKS_SCHEMA", "sensor_readings")
    database = os.getenv("DATABRICKS_DATABASE", "sensor_readings")  # Also check DATABASE
    
    # Use DATABASE if SCHEMA not set
    if not schema or schema == "sensor_data":  # Fix wrong schema
        schema = "sensor_readings"
    
    if not all([host, token, warehouse_id]):
        print("❌ Missing Databricks credentials in .env file")
        print("Required: DATABRICKS_HOST, DATABRICKS_TOKEN, and either:")
        print("  - DATABRICKS_WAREHOUSE_ID, or")
        print("  - DATABRICKS_HTTP_PATH (e.g., /sql/1.0/warehouses/xxxxx)")
        print(f"\nFound: host={bool(host)}, token={bool(token)}, warehouse={bool(warehouse_id)}")
        sys.exit(1)
    
    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")
    
    print(f"🔍 Querying Unity Catalog: {catalog}.{schema}")
    print(f"🏢 Host: {host}")
    print(f"📊 Warehouse: {warehouse_id}\n")
    
    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                # First, query to find all tables in the schema
                print(f"\n🔍 Discovering tables in {catalog}.{schema}...")
                table_query = f"""
                SHOW TABLES IN {catalog}.{schema}
                """
                
                cursor.execute(table_query)
                all_tables = cursor.fetchall()
                
                if not all_tables:
                    print(f"⚠️  No tables found in {catalog}.{schema}")
                    print("   You may need to run the setup or check the catalog/schema names")
                    return
                
                print(f"Found {len(all_tables)} tables:")
                for table_info in all_tables:
                    print(f"  - {table_info[1]}")  # Table name is usually in second column
                
                # Query each discovered table
                results = []
                for table_info in all_tables:
                    table = table_info[1]  # Table name
                    full_table = f"{catalog}.{schema}.{table}"
                    
                    # Check if table has expected columns
                    try:
                        # First check table schema
                        schema_query = f"DESCRIBE {full_table}"
                        cursor.execute(schema_query)
                        columns = [row[0] for row in cursor.fetchall()]
                        
                        # Only query tables with timestamp column
                        if 'timestamp' in columns:
                            # Check if we have turbine_id or sensor_id
                            id_column = 'sensor_id' if 'sensor_id' in columns else 'turbine_id' if 'turbine_id' in columns else None
                            
                            # Get count and date range
                            if id_column:
                                query = f"""
                                SELECT 
                                    '{table}' as table_name,
                                    COUNT(*) as record_count,
                                    MIN(timestamp) as earliest_record,
                                    MAX(timestamp) as latest_record,
                                    COUNT(DISTINCT {id_column}) as unique_sensors
                                FROM {full_table}
                                """
                            else:
                                # No ID column, just get basic stats
                                query = f"""
                                SELECT 
                                    '{table}' as table_name,
                                    COUNT(*) as record_count,
                                    MIN(timestamp) as earliest_record,
                                    MAX(timestamp) as latest_record,
                                    0 as unique_sensors
                                FROM {full_table}
                                """
                            
                            cursor.execute(query)
                            row = cursor.fetchone()
                            if row:
                                results.append(row)
                        else:
                            # Table doesn't have expected schema
                            results.append((table, 0, "No timestamp column", "", 0))
                    except Exception as e:
                        # Error querying table
                        results.append((table, 0, f"Error: {str(e)[:20]}", "", 0))
                
                # Display results in a nice table
                headers = ["Table", "Records", "Earliest", "Latest", "Sensors"]
                print(tabulate(results, headers=headers, tablefmt="grid"))
                
                # Get total summary only if we have results
                if results and any(r[1] > 0 for r in results):
                    print("\n📊 OVERALL SUMMARY")
                    
                    # Build dynamic UNION query based on existing tables with data
                    union_parts = []
                    for r in results:
                        if r[1] > 0 and "Error" not in str(r[2]):  # Has records and no error
                            # Check which ID column exists in this table
                            schema_query = f"DESCRIBE {catalog}.{schema}.{r[0]}"
                            cursor.execute(schema_query)
                            columns = [row[0] for row in cursor.fetchall()]
                            id_col = 'sensor_id' if 'sensor_id' in columns else 'turbine_id' if 'turbine_id' in columns else "'unknown'"
                            
                            union_parts.append(f"""
                                SELECT '{r[0]}' as stage, timestamp, {id_col} as sensor_id 
                                FROM {catalog}.{schema}.{r[0]}
                            """)
                    
                    if union_parts:
                        query = f"""
                        WITH all_data AS (
                            {' UNION ALL '.join(union_parts)}
                        )
                        SELECT 
                            COUNT(*) as total_records,
                            COUNT(DISTINCT sensor_id) as total_sensors,
                            MIN(timestamp) as earliest_data,
                            MAX(timestamp) as latest_data,
                            COUNT(DISTINCT DATE(timestamp)) as days_of_data
                        FROM all_data
                        """
                        
                        try:
                            cursor.execute(query)
                            row = cursor.fetchone()
                            if row:
                                print(f"Total Records: {row[0]:,}")
                                print(f"Total Sensors: {row[1]}")
                                print(f"Date Range: {row[2]} to {row[3]}")
                                print(f"Days of Data: {row[4]}")
                        except Exception as e:
                            print(f"Could not generate overall summary: {e}")
                
                # Show last 10 entries from each table with data
                print("\n📋 LAST 10 ENTRIES FROM EACH TABLE")
                print("=" * 70)
                
                for r in results:
                    if r[1] > 0 and "Error" not in str(r[2]):  # Has records and no error
                        table_name = r[0]
                        full_table = f"{catalog}.{schema}.{table_name}"
                        
                        print(f"\n📊 Table: {table_name} (Last 10 records)")
                        print("-" * 60)
                        
                        # Get column list for this table
                        try:
                            schema_query = f"DESCRIBE {full_table}"
                            cursor.execute(schema_query)
                            columns = [row[0] for row in cursor.fetchall()]
                            
                            # Select key columns if they exist
                            select_cols = []
                            for col in ['timestamp', 'sensor_id', 'temperature', 'humidity', 
                                       'pressure', 'vibration', 'voltage', 'anomaly_flag',
                                       'alert_level', 'sensor_health', 'record_count']:
                                if col in columns:
                                    select_cols.append(col)
                            
                            if select_cols:
                                # Limit columns to avoid too wide output
                                select_cols = select_cols[:8]
                                
                                query = f"""
                                SELECT {', '.join(select_cols)}
                                FROM {full_table}
                                ORDER BY timestamp DESC
                                LIMIT 10
                                """
                                
                                cursor.execute(query)
                                rows = cursor.fetchall()
                                
                                if rows:
                                    # Format timestamps for readability
                                    formatted_rows = []
                                    for row in rows:
                                        formatted_row = []
                                        for i, val in enumerate(row):
                                            if i == 0 and isinstance(val, (datetime, str)):  # timestamp
                                                try:
                                                    if isinstance(val, str):
                                                        formatted_row.append(val[:19])  # YYYY-MM-DD HH:MM:SS
                                                    else:
                                                        formatted_row.append(val.strftime("%Y-%m-%d %H:%M:%S"))
                                                except:
                                                    formatted_row.append(str(val)[:19])
                                            elif isinstance(val, float):
                                                formatted_row.append(f"{val:.2f}")
                                            else:
                                                formatted_row.append(val)
                                        formatted_rows.append(formatted_row)
                                    
                                    print(tabulate(formatted_rows, headers=select_cols, tablefmt="simple"))
                                else:
                                    print("No data found")
                            else:
                                print("Table has unexpected schema")
                                
                        except Exception as e:
                            print(f"Error querying table: {str(e)[:100]}")
                
                # Show recent data ingestion - find a table with data
                for r in results:
                    if r[1] > 0 and "Error" not in str(r[2]):
                        print("\n📈 RECENT INGESTION (Last 24 hours)")
                        query = f"""
                        SELECT 
                            DATE_FORMAT(timestamp, 'yyyy-MM-dd HH:00') as hour,
                            COUNT(*) as records
                        FROM {catalog}.{schema}.{r[0]}
                        WHERE timestamp > CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
                        GROUP BY 1
                        ORDER BY 1 DESC
                        LIMIT 10
                        """
                        
                        try:
                            cursor.execute(query)
                            rows = cursor.fetchall()
                            if rows:
                                print(f"From table: {r[0]}")
                                print(tabulate(rows, headers=["Hour", "Records"], tablefmt="simple"))
                            else:
                                print("No data in the last 24 hours")
                        except:
                            pass
                        break  # Only show for first table with data
                    
    except Exception as e:
        print(f"❌ Error connecting to Databricks: {e}")
        sys.exit(1)

def query_s3_buckets():
    """Query all S3 buckets and show summary."""
    
    print("\n" + "=" * 70)
    print("📦 S3 BUCKET SUMMARY")
    print("=" * 70)
    
    # Get AWS credentials - check multiple sources
    aws_access_key = None
    aws_secret_key = None
    aws_region = os.getenv("AWS_REGION", "us-west-2")
    
    # Try to load from credentials file first
    creds_file = Path("credentials/expanso-s3-env.sh")
    if creds_file.exists():
        print(f"📁 Loading credentials from: {creds_file}")
        with open(creds_file, 'r') as f:
            for line in f:
                if line.startswith("export AWS_ACCESS_KEY_ID="):
                    aws_access_key = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("export AWS_SECRET_ACCESS_KEY="):
                    aws_secret_key = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("export AWS_DEFAULT_REGION="):
                    aws_region = line.split("=", 1)[1].strip().strip("'\"")
    
    # Fall back to environment variables
    if not aws_access_key:
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not aws_access_key or not aws_secret_key:
        print("⚠️  No AWS credentials found. Skipping S3 query.")
        print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or")
        print("   create credentials/expanso-s3-env.sh")
        return
    
    # Create S3 client
    s3_client = boto3.client(
        's3',
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    
    # Define buckets to check - only the ones that actually exist
    bucket_names = {
        "ingestion": "expanso-databricks-ingestion-us-west-2",
        "validated": "expanso-databricks-validated-us-west-2",
        "enriched": "expanso-databricks-enriched-us-west-2",
        "aggregated": "expanso-databricks-aggregated-us-west-2",
    }
    
    results = []
    total_files = 0
    total_size = 0
    
    for bucket_type, bucket_name in bucket_names.items():
        try:
            # List objects in bucket
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name)
            
            file_count = 0
            bucket_size = 0
            latest_modified = None
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        file_count += 1
                        bucket_size += obj.get('Size', 0)
                        obj_modified = obj.get('LastModified')
                        if obj_modified and (not latest_modified or obj_modified > latest_modified):
                            latest_modified = obj_modified
            
            total_files += file_count
            total_size += bucket_size
            
            # Format size
            size_mb = bucket_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
            
            # Format date
            date_str = latest_modified.strftime("%Y-%m-%d %H:%M") if latest_modified else "N/A"
            
            results.append([bucket_type, file_count, size_str, date_str])
            
        except Exception as e:
            if "NoSuchBucket" in str(e):
                results.append([bucket_type, 0, "0 MB", "Bucket not found"])
            else:
                results.append([bucket_type, 0, "0 MB", f"Error: {str(e)[:30]}"])
    
    # Display results
    headers = ["Bucket Type", "Files", "Total Size", "Latest Update"]
    print(tabulate(results, headers=headers, tablefmt="grid"))
    
    # Show totals
    total_size_mb = total_size / (1024 * 1024)
    size_display = f"{total_size_mb:.2f} MB" if total_size_mb < 1024 else f"{total_size_mb/1024:.2f} GB"
    print(f"\n📊 TOTALS: {total_files} files, {size_display}")
    
    # Show recent uploads (last 5 files from any bucket)
    print("\n📤 RECENT UPLOADS (Last 5 files across all buckets):")
    all_files = []
    
    for bucket_type, bucket_name in bucket_names.items():
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=100)
            if 'Contents' in response:
                for obj in response['Contents']:
                    all_files.append({
                        'bucket': bucket_type,
                        'key': obj['Key'][:50] + ('...' if len(obj['Key']) > 50 else ''),
                        'modified': obj['LastModified'],
                        'size': obj['Size'] / 1024  # KB
                    })
        except:
            continue
    
    # Sort by modified date and show last 5
    all_files.sort(key=lambda x: x['modified'], reverse=True)
    recent_files = all_files[:5]
    
    if recent_files:
        recent_data = [[
            f['bucket'],
            f['key'],
            f"{f['size']:.1f} KB",
            f['modified'].strftime("%Y-%m-%d %H:%M")
        ] for f in recent_files]
        
        print(tabulate(recent_data, 
                      headers=["Bucket", "File", "Size", "Modified"],
                      tablefmt="simple"))
    else:
        print("No files found in any bucket")

if __name__ == "__main__":
    # Query both S3 and Unity Catalog
    query_s3_buckets()
    query_unity_catalog()