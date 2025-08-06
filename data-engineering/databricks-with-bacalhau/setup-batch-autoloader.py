#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "requests>=2.31.0",
# ]
# ///

"""Create a batch-based Auto Loader notebook that processes files in cycles."""

import os
import sys
import json
import base64
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_batch_autoloader():
    """Create a batch processing notebook for clusters that don't support continuous streaming."""
    
    # Get Databricks credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    
    if not all([host, token]):
        print("❌ Missing DATABRICKS_HOST or DATABRICKS_TOKEN")
        sys.exit(1)
    
    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")
    base_url = f"https://{host}/api/2.0"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    catalog = os.getenv("DATABRICKS_CATALOG", "expanso_databricks_workspace")
    schema = os.getenv("DATABRICKS_DATABASE", "sensor_data")
    
    print(f"🔄 Creating Batch Auto Loader for {catalog}.{schema}")
    print(f"🏢 Host: {host}\n")
    
    # Batch processing notebook
    batch_notebook = f"""# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Batch Auto Loader - All Pipelines
# MAGIC This notebook processes all available files in batches and runs continuously for 1 hour
# MAGIC 
# MAGIC **Features:**
# MAGIC - ✅ Works with all cluster types (including serverless)
# MAGIC - 📦 Processes all available files in each batch
# MAGIC - ⏰ Auto-stops after 1 hour
# MAGIC - 💰 Cost-optimized with batch processing

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *
import time
from datetime import datetime, timedelta

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"

# Runtime configuration
AUTO_SHUTDOWN_MINUTES = 60  # Total runtime in minutes
BATCH_INTERVAL_SECONDS = 10  # Time between batch runs

# Pipeline configurations
pipelines = {{
    "ingestion": {{
        "source": "s3://expanso-databricks-ingestion-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/ingestion/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_data_ingestion"
    }},
    "validated": {{
        "source": "s3://expanso-databricks-validated-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/validated/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_data_validated"
    }},
    "enriched": {{
        "source": "s3://expanso-databricks-enriched-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/enriched/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_data_enriched"
    }},
    "aggregated": {{
        "source": "s3://expanso-databricks-aggregated-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/aggregated/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_data_aggregated"
    }},
    "emergency": {{
        "source": "s3://expanso-databricks-emergency-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/emergency/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_data_emergency"
    }}
}}

print(f"⚙️  Configuration loaded")
print(f"📊 Target catalog: {{catalog}}.{{schema_name}}")
print(f"⏰ Auto-shutdown after: {{AUTO_SHUTDOWN_MINUTES}} minutes")
print(f"⏱️  Batch interval: {{BATCH_INTERVAL_SECONDS}} seconds")
print(f"🚀 Pipelines: {{', '.join(pipelines.keys())}}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process Files in Batches

# COMMAND ----------

def process_pipeline(name, config):
    \"\"\"Process all available files for a single pipeline.\"\"\"
    try:
        # Read available files using Auto Loader with availableNow trigger
        df = (spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", config["checkpoint"] + "schema")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("multiLine", "true")
            .load(config["source"]))
        
        # Process based on pipeline type
        if name == "aggregated":
            # Pre-aggregated data has different schema
            processed_df = (df
                .select(explode(col("records")).alias("record"))
                .select(
                    col("record.turbine_id"),
                    to_timestamp(col("record.hour")).alias("hour"),
                    col("record.avg_temperature").cast("double"),
                    col("record.avg_humidity").cast("double"),
                    col("record.avg_pressure").cast("double"),
                    col("record.avg_voltage").cast("double"),
                    col("record.record_count").cast("long"),
                    current_timestamp().alias("aggregated_at")
                )
                .filter(col("turbine_id").isNotNull()))
        elif name == "emergency":
            # Emergency data with alert fields
            processed_df = (df
                .select(explode(col("records")).alias("record"))
                .select(
                    col("record.sensor_id").alias("turbine_id"),
                    to_timestamp(col("record.timestamp")).alias("timestamp"),
                    col("record.temperature").cast("double"),
                    col("record.humidity").cast("double"),
                    col("record.pressure").cast("double"),
                    col("record.voltage").cast("double"),
                    col("record.location"),
                    col("record.anomaly_type"),
                    col("record.severity"),
                    col("record.alert_message"),
                    current_timestamp().alias("detected_at")
                )
                .filter(col("turbine_id").isNotNull()))
        else:
            # Standard sensor data processing
            timestamp_col = f"{{name}}_at" if name != "ingestion" else "ingested_at"
            processed_df = (df
                .select(explode(col("records")).alias("record"))
                .select(
                    col("record.sensor_id").alias("turbine_id"),
                    to_timestamp(col("record.timestamp")).alias("timestamp"),
                    col("record.temperature").cast("double"),
                    col("record.humidity").cast("double"),
                    col("record.pressure").cast("double"),
                    col("record.voltage").cast("double"),
                    col("record.location"),
                    current_timestamp().alias(timestamp_col)
                )
                .filter(col("turbine_id").isNotNull()))
        
        # Write using availableNow trigger (process all available and stop)
        query = (processed_df.writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", config["checkpoint"] + "write")
            .trigger(availableNow=True)
            .table(config["table"]))
        
        # Wait for completion
        query.awaitTermination()
        
        # Get processing stats
        if query.lastProgress:
            num_files = query.lastProgress.get("numInputRows", 0)
            return num_files
        return 0
        
    except Exception as e:
        if "Path does not exist" in str(e):
            return 0  # No files to process
        else:
            print(f"   ⚠️  Error in {{name}}: {{str(e)[:100]}}")
            return -1

# COMMAND ----------

# Main processing loop
start_time = datetime.now()
shutdown_time = start_time + timedelta(minutes=AUTO_SHUTDOWN_MINUTES)
batch_number = 0
total_records_processed = {{name: 0 for name in pipelines.keys()}}

print(f"\\n🕐 Start time: {{start_time}}")
print(f"🛑 Scheduled shutdown: {{shutdown_time}}")
print("="*60)

while datetime.now() < shutdown_time:
    batch_number += 1
    batch_start = datetime.now()
    
    print(f"\\n📦 Batch #{{batch_number}} - {{batch_start.strftime('%H:%M:%S')}}")
    print("-"*40)
    
    # Process each pipeline
    batch_processed = {{}}
    for name, config in pipelines.items():
        print(f"   Processing {{name}}...", end="")
        records = process_pipeline(name, config)
        
        if records > 0:
            print(f" ✅ {{records}} records")
            batch_processed[name] = records
            total_records_processed[name] += records
        elif records == 0:
            print(" ⏸️  No new files")
            batch_processed[name] = 0
        else:
            print(" ❌ Error")
            batch_processed[name] = 0
    
    # Show batch summary
    if any(v > 0 for v in batch_processed.values()):
        print(f"\\n   📊 Batch summary:")
        for name, count in batch_processed.items():
            if count > 0:
                print(f"      {{name}}: +{{count}} records")
    
    # Calculate remaining time
    remaining = shutdown_time - datetime.now()
    remaining_minutes = int(remaining.total_seconds() / 60)
    
    print(f"\\n   ⏱️  Time remaining: {{remaining_minutes}} minutes")
    
    # Wait before next batch (unless we're about to shutdown)
    if datetime.now() + timedelta(seconds=BATCH_INTERVAL_SECONDS) < shutdown_time:
        print(f"   💤 Waiting {{BATCH_INTERVAL_SECONDS}} seconds...")
        time.sleep(BATCH_INTERVAL_SECONDS)
    else:
        break

# COMMAND ----------

# MAGIC %md
# MAGIC ## Final Summary

# COMMAND ----------

print("\\n" + "="*60)
print("✅ AUTO LOADER SESSION COMPLETE")
print("="*60)

print(f"\\n📊 PROCESSING SUMMARY:")
print(f"   Total batches: {{batch_number}}")
print(f"   Runtime: {{datetime.now() - start_time}}")

print(f"\\n📈 RECORDS PROCESSED BY PIPELINE:")
for name, count in total_records_processed.items():
    if count > 0:
        print(f"   {{name}}: {{count:,}} records")

print(f"\\n📊 CURRENT TABLE SIZES:")
for name, config in pipelines.items():
    try:
        count = spark.sql(f"SELECT COUNT(*) as cnt FROM {{config['table']}}").collect()[0]["cnt"]
        print(f"   {{name}}: {{count:,}} total records")
    except:
        print(f"   {{name}}: Table not accessible")

print("\\n💡 To restart processing, run this notebook again")
print("✨ Files are tracked via checkpoints, so no duplicates will be processed")
"""
    
    # Create the notebook via API
    print("📓 Creating Batch Auto Loader notebook...\n")
    
    # First create the parent directory
    try:
        mkdir_payload = {"path": "/Shared/AutoLoader"}
        response = requests.post(
            f"{base_url}/workspace/mkdirs",
            headers=headers,
            json=mkdir_payload
        )
        if response.status_code == 200:
            print("✅ Created folder: /Shared/AutoLoader")
    except:
        pass
    
    # Create the batch notebook
    try:
        encoded_content = base64.b64encode(batch_notebook.encode()).decode()
        
        payload = {
            "path": "/Shared/AutoLoader/BATCH_AutoLoader_All_Pipelines",
            "language": "PYTHON",
            "content": encoded_content,
            "overwrite": True
        }
        
        response = requests.post(
            f"{base_url}/workspace/import",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            print("✅ Created batch notebook: /Shared/AutoLoader/BATCH_AutoLoader_All_Pipelines")
        else:
            print(f"⚠️  Issue creating notebook: {response.text}")
            
    except Exception as e:
        print(f"❌ Error creating notebook: {e}")
    
    print("\n" + "="*70)
    print("🎯 BATCH AUTO LOADER SETUP COMPLETE!")
    print("="*70)
    print("\n📋 TO START BATCH PROCESSING:")
    print("-" * 40)
    print("1. Go to Databricks UI:")
    print(f"   https://{host}/")
    print("\n2. Navigate to:")
    print("   /Shared/AutoLoader/BATCH_AutoLoader_All_Pipelines")
    print("\n3. Attach to any cluster type (including serverless)")
    print("4. Click 'Run All'")
    print("\n✨ FEATURES:")
    print("   • Works with ALL cluster types")
    print("   • Processes files in batches every 10 seconds")
    print("   • Auto-stops after 1 hour")
    print("   • Shows processing statistics")
    print("   • Maintains checkpoints (no duplicates)")
    print("\n💡 TO SCHEDULE AS A JOB:")
    print("   1. Go to Workflows → Create Job")
    print("   2. Add task → Notebook → Select BATCH_AutoLoader_All_Pipelines")
    print("   3. Use Serverless compute for best cost savings")
    print("   4. Schedule hourly/daily as needed")

if __name__ == "__main__":
    create_batch_autoloader()
    print("\n✅ Batch Auto Loader setup complete!")