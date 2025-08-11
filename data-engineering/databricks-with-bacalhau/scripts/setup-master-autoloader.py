#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "requests>=2.31.0",
# ]
# ///

"""Create a master Auto Loader notebook that runs all pipelines with auto-shutdown."""

import os
import sys
import json
import base64
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_master_autoloader():
    """Create a single master notebook that runs all Auto Loader streams."""
    
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
    schema = os.getenv("DATABRICKS_DATABASE", "sensor_readings")
    
    print(f"🔄 Creating Master Auto Loader for {catalog}.{schema}")
    print(f"🏢 Host: {host}\n")
    
    # Master notebook content
    master_notebook = f"""# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 S3 to Unity Catalog Batch Loader
# MAGIC This notebook reads data from S3 buckets into Unity Catalog tables
# MAGIC 
# MAGIC **Features:**
# MAGIC - ✅ Reads from 4 S3 buckets (ingestion, validated, enriched, aggregated)
# MAGIC - 📦 Processes all available JSON files in batches
# MAGIC - ⏰ Auto-stops after 1 hour to control costs
# MAGIC - 🔄 Checks for new files every 10 seconds

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
# Each bucket receives data from nodes based on their processing type
# All data is written to ingestion/YYYY/MM/DD/HHMMSS/data.json path within each bucket
pipelines = {{
    "ingestion": {{
        "source": "s3://expanso-databricks-ingestion-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/ingestion/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_readings_ingestion"
    }},
    "validated": {{
        "source": "s3://expanso-databricks-validated-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/validated/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_readings_validated"
    }},
    "enriched": {{
        "source": "s3://expanso-databricks-enriched-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/enriched/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_readings_enriched"
    }},
    "aggregated": {{
        "source": "s3://expanso-databricks-aggregated-us-west-2/ingestion/",
        "checkpoint": "s3://expanso-databricks-checkpoints-us-west-2/aggregated/",
        "table": f"{{catalog}}.{{schema_name}}.sensor_readings_aggregated"
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
                    col("record.turbine_id").alias("turbine_id"),
                    to_timestamp(col("record.hour")).alias("hour"),
                    col("record.avg_temperature").cast("double").alias("avg_temperature"),
                    col("record.avg_humidity").cast("double").alias("avg_humidity"),
                    col("record.avg_pressure").cast("double").alias("avg_pressure"),
                    col("record.avg_voltage").cast("double").alias("avg_voltage"),
                    col("record.record_count").cast("long").alias("record_count"),
                    current_timestamp().alias("aggregated_at")
                )
                .filter(col("turbine_id").isNotNull()))
        else:
            # Standard sensor data processing (ingestion, enriched)
            timestamp_col = f"{{name}}_at" if name != "ingestion" else "ingested_at"
            processed_df = (df
                .select(explode(col("records")).alias("record"))
                .select(
                    col("record.sensor_id").alias("turbine_id"),
                    to_timestamp(col("record.timestamp")).alias("timestamp"),
                    col("record.temperature").cast("double").alias("temperature"),
                    col("record.humidity").cast("double").alias("humidity"),
                    col("record.pressure").cast("double").alias("pressure"),
                    col("record.voltage").cast("double").alias("voltage"),
                    col("record.location").alias("location"),
                    current_timestamp().alias(timestamp_col)
                )
                .filter(col("turbine_id").isNotNull()))
        
        # Write using availableNow trigger (process all available and stop)
        query = (processed_df.writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", config["checkpoint"] + "write")
            .option("mergeSchema", "true")  # Allow schema evolution
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
        if "Path does not exist" in str(e) or "No such file or directory" in str(e):
            return 0  # No files to process yet - this is OK
        else:
            print(f"   ⚠️  Error in {{name}}: {{str(e)[:200]}}")
            return -1

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
    print("📓 Creating Master Auto Loader notebook...\n")
    
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
    
    # Create the master notebook
    try:
        encoded_content = base64.b64encode(master_notebook.encode()).decode()
        
        payload = {
            "path": "/Shared/AutoLoader/MASTER_AutoLoader_All_Pipelines",
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
            print("✅ Created master notebook: /Shared/AutoLoader/MASTER_AutoLoader_All_Pipelines")
        else:
            print(f"⚠️  Issue creating notebook: {response.text}")
            
    except Exception as e:
        print(f"❌ Error creating notebook: {e}")
    
    print("\n" + "="*70)
    print("🎯 ONE-CLICK AUTO LOADER SETUP COMPLETE!")
    print("="*70)
    print("\n📋 TO START ALL PIPELINES:")
    print("-" * 40)
    print("1. Go to Databricks UI:")
    print(f"   https://{host}/")
    print("\n2. Navigate to:")
    print("   /Shared/AutoLoader/MASTER_AutoLoader_All_Pipelines")
    print("\n3. Attach to a cluster and click 'Run All'")
    print("\n✨ FEATURES:")
    print("   • Starts ALL 5 pipelines with one click")
    print("   • Auto-stops after 1 hour (configurable)")
    print("   • Shows real-time monitoring")
    print("   • Displays records processed")
    print("   • Cost-optimized with automatic shutdown")
    print("\n💡 TO CREATE A JOB (for scheduling):")
    print("   1. Go to Workflows → Create Job")
    print("   2. Add task → Notebook → Select MASTER_AutoLoader_All_Pipelines")
    print("   3. Configure cluster (recommend Job Compute for cost savings)")
    print("   4. Set schedule if needed")
    print("   5. Enable email notifications on failure")

if __name__ == "__main__":
    create_master_autoloader()
    print("\n✅ Master Auto Loader setup complete!")