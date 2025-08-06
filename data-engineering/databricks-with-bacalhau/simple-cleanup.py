#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

"""Simple cleanup of Unity Catalog tables."""

import os
import sys
from dotenv import load_dotenv
from databricks import sql

# Load environment variables
load_dotenv()

def simple_cleanup():
    """Drop problematic tables directly."""
    
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
    
    print(f"🧹 Cleaning up tables in {catalog}.{schema}\n")
    
    # Tables to DROP (problematic tables)
    tables_to_drop = [
        "sensor_data_emergency",
        "sensor_data_filtered", 
        "sensor_data_raw",
        "sensor_data_schematized",
    ]
    
    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                
                print("📋 Current tables:")
                cursor.execute(f"""
                    SELECT table_name 
                    FROM {catalog}.information_schema.tables 
                    WHERE table_schema = '{schema}'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                for table in tables:
                    print(f"  - {table[0]}")
                
                print("\n🗑️  Dropping problematic tables...")
                for table in tables_to_drop:
                    try:
                        print(f"  Dropping: {table}", end="")
                        cursor.execute(f"DROP TABLE IF EXISTS {catalog}.{schema}.{table}")
                        print(" ✅")
                    except Exception as e:
                        print(f" ⚠️  {str(e)[:50]}")
                
                print("\n✅ Tables after cleanup:")
                cursor.execute(f"""
                    SELECT table_name 
                    FROM {catalog}.information_schema.tables 
                    WHERE table_schema = '{schema}'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                for table in tables:
                    table_name = table[0]
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {catalog}.{schema}.{table_name}")
                        count = cursor.fetchone()[0]
                        print(f"  - {table_name}: {count:,} records")
                    except:
                        print(f"  - {table_name}")
                
                # Create a simple monitoring view
                print("\n📐 Creating monitoring view...")
                try:
                    cursor.execute(f"DROP VIEW IF EXISTS {catalog}.{schema}.pipeline_status")
                    
                    cursor.execute(f"""
                        CREATE VIEW {catalog}.{schema}.pipeline_status AS
                        SELECT 
                            'ingestion' as pipeline,
                            COUNT(*) as record_count,
                            MAX(ingested_at) as last_update
                        FROM {catalog}.{schema}.sensor_data_ingestion
                        UNION ALL
                        SELECT 
                            'enriched' as pipeline,
                            COUNT(*) as record_count,
                            MAX(enriched_at) as last_update
                        FROM {catalog}.{schema}.sensor_data_enriched
                        UNION ALL
                        SELECT 
                            'validated' as pipeline,
                            COUNT(*) as record_count,
                            MAX(validated_at) as last_update
                        FROM {catalog}.{schema}.sensor_data_validated
                        UNION ALL
                        SELECT 
                            'aggregated' as pipeline,
                            COUNT(*) as record_count,
                            MAX(aggregated_at) as last_update
                        FROM {catalog}.{schema}.sensor_data_aggregated
                    """)
                    print("  ✅ Created view: pipeline_status")
                    
                    # Query the view
                    cursor.execute(f"SELECT * FROM {catalog}.{schema}.pipeline_status ORDER BY record_count DESC")
                    results = cursor.fetchall()
                    
                    print("\n📊 Pipeline Status:")
                    for row in results:
                        pipeline = row[0]
                        count = row[1]
                        last_update = row[2] if row[2] else "No data"
                        print(f"  - {pipeline}: {count:,} records (last: {last_update})")
                    
                except Exception as e:
                    print(f"  ⚠️  Could not create view: {str(e)[:100]}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    simple_cleanup()
    print("\n✅ Cleanup complete!")