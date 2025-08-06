#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

"""Clean up duplicate/unnecessary tables in Databricks."""

import os
import sys
from dotenv import load_dotenv
from databricks import sql

# Load environment variables
load_dotenv()

def cleanup_tables():
    """Drop unnecessary tables and keep only the ones we need."""
    
    # Get Databricks credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    
    # Extract warehouse ID from HTTP_PATH
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
        if "/warehouses/" in http_path:
            warehouse_id = http_path.split("/warehouses/")[-1]
    
    catalog = os.getenv("DATABRICKS_CATALOG", "expanso_databricks_workspace")
    schema = os.getenv("DATABRICKS_DATABASE", "sensor_data")
    
    if not all([host, token, warehouse_id]):
        print("❌ Missing Databricks credentials")
        sys.exit(1)
    
    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")
    
    print(f"🧹 Cleaning up tables in {catalog}.{schema}")
    
    # Tables to DROP (old/duplicate tables)
    tables_to_drop = [
        "aggregated_sensor_data",
        "anomaly_notifications",
        "error_sensor_data",
        "raw_sensor_data",
        "schematized_sensor_data",
    ]
    
    # Tables to KEEP and ensure they exist with correct schema
    tables_to_keep = {
        "sensor_data_ingestion": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sensor_data_ingestion (
                turbine_id STRING,
                timestamp TIMESTAMP,
                temperature DOUBLE,
                humidity DOUBLE,
                pressure DOUBLE,
                voltage DOUBLE,
                location STRING,
                ingested_at TIMESTAMP
            ) USING DELTA
            LOCATION 's3://expanso-databricks-ingestion-us-west-2/data/'
        """,
        "sensor_data_validated": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sensor_data_validated (
                turbine_id STRING,
                timestamp TIMESTAMP,
                temperature DOUBLE,
                humidity DOUBLE,
                pressure DOUBLE,
                voltage DOUBLE,
                location STRING,
                validated_at TIMESTAMP
            ) USING DELTA
            LOCATION 's3://expanso-databricks-validated-us-west-2/data/'
        """,
        "sensor_data_enriched": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sensor_data_enriched (
                turbine_id STRING,
                timestamp TIMESTAMP,
                temperature DOUBLE,
                humidity DOUBLE,
                pressure DOUBLE,
                voltage DOUBLE,
                location STRING,
                enriched_at TIMESTAMP
            ) USING DELTA
            LOCATION 's3://expanso-databricks-enriched-us-west-2/data/'
        """,
        "sensor_data_aggregated": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sensor_data_aggregated (
                turbine_id STRING,
                hour TIMESTAMP,
                avg_temperature DOUBLE,
                avg_humidity DOUBLE,
                avg_pressure DOUBLE,
                avg_voltage DOUBLE,
                record_count BIGINT,
                aggregated_at TIMESTAMP
            ) USING DELTA
            LOCATION 's3://expanso-databricks-aggregated-us-west-2/data/'
        """
    }
    
    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                # Drop old tables
                print("\n🗑️  Dropping old/duplicate tables...")
                for table in tables_to_drop:
                    try:
                        drop_sql = f"DROP TABLE IF EXISTS {catalog}.{schema}.{table}"
                        print(f"  Dropping: {table}")
                        cursor.execute(drop_sql)
                        print(f"  ✅ Dropped: {table}")
                    except Exception as e:
                        print(f"  ⚠️  Could not drop {table}: {e}")
                
                # Recreate/ensure correct tables exist
                print("\n🏗️  Creating/verifying tables with correct schema...")
                for table_name, create_sql in tables_to_keep.items():
                    try:
                        # First drop if exists to ensure clean state
                        drop_sql = f"DROP TABLE IF EXISTS {catalog}.{schema}.{table_name}"
                        cursor.execute(drop_sql)
                        
                        # Create with correct schema
                        formatted_sql = create_sql.format(catalog=catalog, schema=schema)
                        print(f"  Creating: {table_name}")
                        cursor.execute(formatted_sql)
                        print(f"  ✅ Created: {table_name}")
                    except Exception as e:
                        print(f"  ❌ Error with {table_name}: {e}")
                
                # Show final table list
                print("\n📋 Final table list:")
                cursor.execute(f"SHOW TABLES IN {catalog}.{schema}")
                tables = cursor.fetchall()
                for table in tables:
                    print(f"  - {table[1]}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cleanup_tables()
    print("\n✅ Cleanup complete!")