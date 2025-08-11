#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "requests>=2.31.0",
# ]
# ///

"""Setup streaming Auto Loader jobs to continuously monitor S3 for new files."""

import os
import sys
import json
import requests
from dotenv import load_dotenv
from databricks import sql

# Load environment variables
load_dotenv()

def create_autoloader_notebooks():
    """Create Databricks notebooks for Auto Loader streaming jobs."""
    
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
    
    print(f"🔄 Setting up Streaming Auto Loader for {catalog}.{schema}")
    print(f"🏢 Host: {host}\n")
    
    # Define notebook content for each pipeline
    notebooks = [
        {
            "path": "/Shared/AutoLoader/ingestion_streaming",
            "name": "Ingestion Pipeline - Streaming",
            "content": f"""# Databricks notebook source
# MAGIC %md
# MAGIC ## Streaming Auto Loader - Ingestion Pipeline
# MAGIC This notebook continuously monitors S3 for new sensor data files

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"
source_path = "s3://expanso-databricks-ingestion-us-west-2/ingestion/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/ingestion/"
target_table = f"{{catalog}}.{{schema_name}}.sensor_readings_ingestion"

# COMMAND ----------

# Define schema for the JSON records
record_schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("timestamp", StringType(), True),
    StructField("sensor_id", StringType(), True),
    StructField("temperature", DoubleType(), True),
    StructField("humidity", DoubleType(), True),
    StructField("pressure", DoubleType(), True),
    StructField("voltage", DoubleType(), True),
    StructField("vibration", DoubleType(), True),
    StructField("location", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("status_code", IntegerType(), True),
    StructField("anomaly_flag", IntegerType(), True),
    StructField("firmware_version", StringType(), True),
    StructField("model", StringType(), True),
    StructField("manufacturer", StringType(), True)
])

# COMMAND ----------

# Read streaming data using Auto Loader
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("multiLine", "true")
    .load(source_path))

# COMMAND ----------

# Process the data - explode records array and transform
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
        current_timestamp().alias("ingested_at")
    )
    .filter(col("turbine_id").isNotNull())
)

# COMMAND ----------

# Write stream to Delta table
query = (processed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_path + "write")
    .trigger(processingTime='10 seconds')  # Process every 10 seconds
    .table(target_table))

# COMMAND ----------

# Display streaming progress
display(query.status)
"""
        },
        {
            "path": "/Shared/AutoLoader/enriched_streaming",
            "name": "Enriched Pipeline - Streaming",
            "content": f"""# Databricks notebook source
# MAGIC %md
# MAGIC ## Streaming Auto Loader - Enriched Pipeline
# MAGIC This notebook continuously monitors S3 for enriched sensor data

# COMMAND ----------

from pyspark.sql.functions import *

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"
source_path = "s3://expanso-databricks-enriched-us-west-2/ingestion/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/enriched/"
target_table = f"{{catalog}}.{{schema_name}}.sensor_readings_enriched"

# COMMAND ----------

# Read streaming data using Auto Loader
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("multiLine", "true")
    .load(source_path))

# COMMAND ----------

# Process the data
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
        current_timestamp().alias("enriched_at")
    )
    .filter(col("turbine_id").isNotNull())
)

# COMMAND ----------

# Write stream to Delta table
query = (processed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_path + "write")
    .trigger(processingTime='10 seconds')  # Process every 10 seconds
    .table(target_table))

# COMMAND ----------

# Monitor the stream
display(query.status)
"""
        },
        {
            "path": "/Shared/AutoLoader/validated_streaming",
            "name": "Validated Pipeline - Streaming",
            "content": f"""# Databricks notebook source
# MAGIC %md
# MAGIC ## Streaming Auto Loader - Validated Pipeline
# MAGIC This notebook monitors S3 for validated sensor data

# COMMAND ----------

from pyspark.sql.functions import *

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"
source_path = "s3://expanso-databricks-validated-us-west-2/ingestion/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/validated/"
target_table = f"{{catalog}}.{{schema_name}}.sensor_readings_validated"

# COMMAND ----------

# Read streaming data using Auto Loader
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("multiLine", "true")
    .load(source_path))

# COMMAND ----------

# Process the data
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
        current_timestamp().alias("validated_at")
    )
    .filter(col("turbine_id").isNotNull())
)

# COMMAND ----------

# Write stream to Delta table
query = (processed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_path + "write")
    .trigger(processingTime='10 seconds')  # Process every 10 seconds
    .table(target_table))

# COMMAND ----------

display(query.status)
"""
        },
        {
            "path": "/Shared/AutoLoader/aggregated_streaming",
            "name": "Aggregated Pipeline - Streaming",
            "content": f"""# Databricks notebook source
# MAGIC %md
# MAGIC ## Streaming Auto Loader - Aggregated Pipeline
# MAGIC This notebook monitors S3 for pre-aggregated data

# COMMAND ----------

from pyspark.sql.functions import *

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"
source_path = "s3://expanso-databricks-aggregated-us-west-2/ingestion/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/aggregated/"
target_table = f"{{catalog}}.{{schema_name}}.sensor_readings_aggregated"

# COMMAND ----------

# Read streaming data using Auto Loader
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("multiLine", "true")
    .load(source_path))

# COMMAND ----------

# Process pre-aggregated data from S3
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
    .filter(col("turbine_id").isNotNull())
)

# COMMAND ----------

# Write stream to Delta table
query = (processed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_path + "write")
    .trigger(processingTime='10 seconds')  # Check every 10 seconds
    .table(target_table))

# COMMAND ----------

display(query.status)
"""
        },
        {
            "path": "/Shared/AutoLoader/emergency_streaming",
            "name": "Emergency Pipeline - Streaming",
            "content": f"""# Databricks notebook source
# MAGIC %md
# MAGIC ## Streaming Auto Loader - Emergency Pipeline
# MAGIC This notebook monitors S3 for emergency/anomaly data requiring immediate attention

# COMMAND ----------

from pyspark.sql.functions import *

# Configuration
catalog = "{catalog}"
schema_name = "{schema}"
source_path = "s3://expanso-databricks-emergency-us-west-2/ingestion/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/emergency/"
target_table = f"{{catalog}}.{{schema_name}}.sensor_readings_emergency"

# COMMAND ----------

# Read streaming data using Auto Loader - check more frequently for emergencies
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("multiLine", "true")
    .load(source_path))

# COMMAND ----------

# Process emergency data
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
    .filter(col("turbine_id").isNotNull())
)

# COMMAND ----------

# Write stream to Delta table with immediate processing
query = (processed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_path + "write")
    .trigger(processingTime='5 seconds')  # Check every 5 seconds for emergencies
    .table(target_table))

# COMMAND ----------

# Alert on new emergencies (optional - add your alerting logic here)
# For example: send to SNS, email, Slack, etc.

display(query.status)
"""
        }
    ]
    
    # Create notebooks via API
    print("📓 Creating Auto Loader notebooks...\n")
    
    # First create the parent directory
    try:
        mkdir_payload = {
            "path": "/Shared/AutoLoader"
        }
        response = requests.post(
            f"{base_url}/workspace/mkdirs",
            headers=headers,
            json=mkdir_payload
        )
        if response.status_code == 200:
            print("✅ Created folder: /Shared/AutoLoader\n")
        else:
            print(f"⚠️  Folder might already exist: {response.text}\n")
    except Exception as e:
        print(f"⚠️  Could not create folder: {e}\n")
    
    for notebook in notebooks:
        try:
            # Create the notebook
            import base64
            encoded_content = base64.b64encode(notebook["content"].encode()).decode()
            
            payload = {
                "path": notebook["path"],
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
                print(f"✅ Created notebook: {notebook['path']}")
                print(f"   {notebook['name']}")
            else:
                print(f"⚠️  Issue with {notebook['path']}: {response.text}")
                
        except Exception as e:
            print(f"❌ Error creating {notebook['path']}: {e}")
    
    print("\n" + "=" * 60)
    print("📋 SETUP COMPLETE - Next Steps:")
    print("=" * 60)
    print("\n1. Go to Databricks UI")
    print(f"   https://{host}/")
    print("\n2. Navigate to the notebooks:")
    print("   - /Shared/AutoLoader/ingestion_streaming")
    print("   - /Shared/AutoLoader/validated_streaming")
    print("   - /Shared/AutoLoader/enriched_streaming")
    print("   - /Shared/AutoLoader/aggregated_streaming")
    print("   - /Shared/AutoLoader/emergency_streaming")
    print("\n3. For each notebook:")
    print("   a. Open the notebook")
    print("   b. Attach it to a cluster")
    print("   c. Click 'Run All' to start streaming")
    print("\n4. Alternative: Create a Workflow/Job:")
    print("   - Go to Workflows → Create Job")
    print("   - Add task for each notebook")
    print("   - Set to run continuously")
    print("   - Enable retries on failure")
    print("\n📊 The streams will:")
    print("   • Check for new files every 10 seconds")
    print("   • Process multiple files in parallel")
    print("   • Handle late-arriving data")
    print("   • Maintain exactly-once processing guarantees")
    print("   • Store checkpoints in S3 for fault tolerance")

def setup_sql_warehouse_alerts():
    """Setup alerts for monitoring."""
    
    # Get credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    
    if not warehouse_id:
        http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
        if "/warehouses/" in http_path:
            warehouse_id = http_path.split("/warehouses/")[-1]
    
    catalog = os.getenv("DATABRICKS_CATALOG", "expanso_databricks_workspace")
    schema = os.getenv("DATABRICKS_DATABASE", "sensor_readings")
    
    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")
    
    print("\n" + "=" * 60)
    print("🔔 MONITORING SETUP")
    print("=" * 60)
    
    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                # Create monitoring view
                monitoring_sql = f"""
                CREATE OR REPLACE VIEW {catalog}.{schema}.pipeline_monitoring AS
                SELECT 
                    'ingestion' as pipeline,
                    COUNT(*) as total_records,
                    MAX(ingested_at) as last_update
                FROM {catalog}.{schema}.sensor_readings_ingestion
                UNION ALL
                SELECT 
                    'enriched' as pipeline,
                    COUNT(*) as total_records,
                    MAX(enriched_at) as last_update
                FROM {catalog}.{schema}.sensor_readings_enriched
                """
                
                cursor.execute(monitoring_sql)
                print("✅ Created monitoring view: pipeline_monitoring")
                print("\nQuery this view to check pipeline status:")
                print(f"SELECT * FROM {catalog}.{schema}.pipeline_monitoring")
                
    except Exception as e:
        print(f"⚠️  Could not create monitoring view: {e}")

if __name__ == "__main__":
    create_autoloader_notebooks()
    setup_sql_warehouse_alerts()
    print("\n✅ Auto Loader streaming setup complete!")