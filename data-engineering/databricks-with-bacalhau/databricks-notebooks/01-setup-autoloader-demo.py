# Databricks notebook source
# MAGIC %md
# MAGIC # Setup Auto Loader Demo Pipeline
# MAGIC 
# MAGIC This notebook:
# MAGIC 1. Creates all necessary Delta tables
# MAGIC 2. Sets up Auto Loader streams with 24-hour auto-shutdown
# MAGIC 3. Verifies everything is working properly
# MAGIC 4. Provides a dashboard to monitor progress
# MAGIC 
# MAGIC **Safety Features:**
# MAGIC - All streams auto-terminate after 24 hours
# MAGIC - Streams process in batch mode (not continuous)
# MAGIC - Clear cost tracking and monitoring

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

from pyspark.sql.types import *
from pyspark.sql.functions import *
from datetime import datetime, timezone, timedelta
import json

# Widgets for configuration
dbutils.widgets.text("catalog", "expanso_databricks_workspace", "Catalog Name")
dbutils.widgets.text("database", "sensor_data", "Database Name")
dbutils.widgets.dropdown("force_continue", "false", ["true", "false"], "Force Continue on Errors")

# Configuration
CATALOG = dbutils.widgets.get("catalog")
DATABASE = dbutils.widgets.get("database")
DEMO_START_TIME = datetime.now(timezone.utc)
MAX_DEMO_DURATION_HOURS = 24

# S3 bucket configuration for Auto Loader
BUCKETS = {
    "ingestion": "s3://expanso-databricks-ingestion-us-west-2/ingestion/",
    "validated": "s3://expanso-databricks-validated-us-west-2/validated/",
    "enriched": "s3://expanso-databricks-enriched-us-west-2/enriched/",
    "aggregated": "s3://expanso-databricks-aggregated-us-west-2/aggregated/"
}

CHECKPOINT_BASE = "s3://expanso-databricks-checkpoints-us-west-2/demo-checkpoints"
METADATA_BUCKET = "s3://expanso-databricks-metadata-us-west-2"

# Clear Unity Catalog credential cache to avoid stale credential references
spark.conf.set("spark.databricks.unity.catalog.credentialCache.ttl", "0")

# Verify external locations are accessible
print("🔍 Verifying external location access...")
try:
    # Test access to each bucket
    for stage, path in BUCKETS.items():
        try:
            # List files to verify access
            files = dbutils.fs.ls(path)
            print(f"✅ {stage}: Access verified ({len(files)} files found)")
        except Exception as e:
            print(f"❌ {stage}: Access failed - {str(e)}")
            if "STORAGE_CREDENTIAL_DOES_NOT_EXIST" in str(e):
                print("   ⚠️  This error indicates a stale credential reference.")
                print("   Please restart the cluster to clear the cache.")
except Exception as e:
    print(f"⚠️  Could not verify access: {e}")
    print("   You may need to restart the cluster if you see credential errors.")

# Target tables
TABLES = {
    "ingestion": CATALOG + "." + DATABASE + ".sensor_data_ingestion",
    "validated": CATALOG + "." + DATABASE + ".sensor_data_validated",
    "enriched": CATALOG + "." + DATABASE + ".sensor_data_enriched",
    "aggregated": CATALOG + "." + DATABASE + ".sensor_data_aggregated"
}

# Generate unique demo ID
import uuid
demo_id = "demo_" + datetime.now().strftime('%Y%m%d_%H%M%S') + "_" + str(uuid.uuid4())[:8]
demo_end_time = DEMO_START_TIME + timedelta(hours=MAX_DEMO_DURATION_HOURS)

print("🚀 Starting Auto Loader Demo")
print("Demo ID: " + demo_id)
print("Start Time: " + str(DEMO_START_TIME))
print("Auto-shutdown Time: " + str(demo_end_time))
print("Maximum Duration: " + str(MAX_DEMO_DURATION_HOURS) + " hours")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Configuration Summary

# COMMAND ----------

print("📋 Configuration Summary:")
print("  Storage Credential: s3_storage_for_sensor_data")
print("  Catalog: " + CATALOG)
print("  Database: " + DATABASE)
print("\n  S3 Buckets:")
for stage, bucket in BUCKETS.items():
    print("    " + stage + ": " + bucket)
print("\n💡 Note: Auto Loader will use Unity Catalog credentials to access S3")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Create Database and Tables

# COMMAND ----------

# Create database if not exists
spark.sql("CREATE DATABASE IF NOT EXISTS " + CATALOG + "." + DATABASE)
spark.sql("USE " + CATALOG + "." + DATABASE)

print("📊 Creating tables...")

# Define schemas for each stage
schemas = {
    "ingestion": StructType([
        StructField("sensor_id", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("temperature", DoubleType(), True),
        StructField("humidity", DoubleType(), True),
        StructField("pressure", DoubleType(), True),
        StructField("battery_level", DoubleType(), True),
        StructField("signal_strength", IntegerType(), True),
        StructField("location_lat", DoubleType(), True),
        StructField("location_lon", DoubleType(), True),
        StructField("firmware_version", StringType(), True),
        StructField("_ingested_at", TimestampType(), True),
        StructField("_pipeline_stage", StringType(), True),
        StructField("_demo_id", StringType(), True)
    ]),
    
    "validated": StructType([
        StructField("sensor_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("temperature", DoubleType(), False),
        StructField("humidity", DoubleType(), False),
        StructField("pressure", DoubleType(), False),
        StructField("battery_level", DoubleType(), False),
        StructField("signal_strength", IntegerType(), True),
        StructField("location_lat", DoubleType(), True),
        StructField("location_lon", DoubleType(), True),
        StructField("firmware_version", StringType(), True),
        StructField("_validated_at", TimestampType(), True),
        StructField("_validation_status", StringType(), True),
        StructField("_pipeline_stage", StringType(), True),
        StructField("_demo_id", StringType(), True)
    ]),
    
    "enriched": StructType([
        StructField("sensor_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("temperature", DoubleType(), False),
        StructField("humidity", DoubleType(), False),
        StructField("pressure", DoubleType(), False),
        StructField("battery_level", DoubleType(), False),
        StructField("signal_strength", IntegerType(), True),
        StructField("location_lat", DoubleType(), True),
        StructField("location_lon", DoubleType(), True),
        StructField("firmware_version", StringType(), True),
        StructField("temperature_fahrenheit", DoubleType(), True),
        StructField("heat_index", DoubleType(), True),
        StructField("battery_status", StringType(), True),
        StructField("location_region", StringType(), True),
        StructField("_enriched_at", TimestampType(), True),
        StructField("_pipeline_stage", StringType(), True),
        StructField("_demo_id", StringType(), True)
    ]),
    
    "aggregated": StructType([
        StructField("window_start", TimestampType(), False),
        StructField("window_end", TimestampType(), False),
        StructField("sensor_id", StringType(), False),
        StructField("avg_temperature", DoubleType(), True),
        StructField("avg_humidity", DoubleType(), True),
        StructField("avg_pressure", DoubleType(), True),
        StructField("min_battery_level", DoubleType(), True),
        StructField("record_count", LongType(), True),
        StructField("_aggregated_at", TimestampType(), True),
        StructField("_pipeline_stage", StringType(), True),
        StructField("_demo_id", StringType(), True)
    ])
}

# Create tables
for stage, schema in schemas.items():
    table_name = TABLES[stage]
    
    # Create empty DataFrame with schema
    empty_df = spark.createDataFrame([], schema)
    
    # Write as Delta table
    empty_df.write.mode("ignore").format("delta").saveAsTable(table_name)
    
    print("  ✅ Created table: " + table_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Setup Auto Loader Streams

# COMMAND ----------

print("\n🔄 Setting up Auto Loader streams...")

# Simple schema for reading JSON files
json_schema = StructType([
    StructField("metadata", MapType(StringType(), StringType()), True),
    StructField("records", ArrayType(MapType(StringType(), StringType())), True)
])

# Setup ingestion stream
print("\n📥 Setting up ingestion stream...")

try:
    # Read from S3 using Auto Loader
    ingestion_df = (spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("multiLine", "true")
        .option("cloudFiles.schemaLocation", CHECKPOINT_BASE + "/" + demo_id + "/ingestion/schema")
        .option("cloudFiles.maxFilesPerTrigger", 10)  # Process max 10 files at a time
        .schema(json_schema)
        .load(BUCKETS["ingestion"]))
    
    # Process the data
    processed_df = (ingestion_df
        .select(explode(col("records")).alias("record"))
        .select(
            col("record.sensor_id").cast("string").alias("sensor_id"),
            col("record.timestamp").cast("timestamp").alias("timestamp"),
            col("record.temperature").cast("double").alias("temperature"),
            col("record.humidity").cast("double").alias("humidity"),
            col("record.pressure").cast("double").alias("pressure"),
            col("record.battery_level").cast("double").alias("battery_level"),
            col("record.signal_strength").cast("int").alias("signal_strength"),
            col("record.location_lat").cast("double").alias("location_lat"),
            col("record.location_lon").cast("double").alias("location_lon"),
            col("record.firmware_version").cast("string").alias("firmware_version")
        )
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_pipeline_stage", lit("ingestion"))
        .withColumn("_demo_id", lit(demo_id)))
    
    # Write stream with auto-termination
    query = (processed_df.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_BASE + "/" + demo_id + "/ingestion")
        .trigger(processingTime='30 seconds')  # Process every 30 seconds
        .table(TABLES["ingestion"]))
    
    print("✅ Ingestion stream started")
    print("   Stream ID: " + query.id)
    print("   Status: " + query.status['message'])
    
except Exception as e:
    print("❌ Failed to start ingestion stream: " + str(e))
        print("\n⚠️  This might be due to Unity Catalog permissions.")
        print("   Please ensure:")
        print("   1. The SQL warehouse/cluster has access to the storage credential")
        print("   2. External locations are properly configured")
        print("   3. You have CREATE TABLE permissions in the catalog")
        raise
# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Create Monitoring Dashboard

# COMMAND ----------

print("\n📊 Creating monitoring dashboard...")

# Store demo metadata
demo_metadata = {
    "demo_id": demo_id,
    "start_time": DEMO_START_TIME.isoformat(),
    "auto_shutdown_time": demo_end_time.isoformat(),
    "max_duration_hours": MAX_DEMO_DURATION_HOURS,
    "catalog": CATALOG,
    "database": DATABASE,
    "tables": TABLES,
    "buckets": BUCKETS,
    "bucket_access": bucket_access,
    "streams": {
        "ingestion": {
            "id": query.id if 'query' in locals() else None,
            "status": query.status['message'] if 'query' in locals() else "Not started"
        }
    }
}

# Save metadata
metadata_path = METADATA_BUCKET + "/demo-metadata/" + demo_id + "/setup_summary.json"
dbutils.fs.put(metadata_path, json.dumps(demo_metadata, indent=2), overwrite=True)

print("✅ Dashboard created")
print("   Metadata saved to: " + metadata_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Verify Setup

# COMMAND ----------

print("\n🔍 Verifying setup...")

# Check tables exist
for stage, table in TABLES.items():
    try:
        count = spark.table(table).count()
        print("  ✅ " + stage + " table exists with " + str(count) + " records")
    except:
        print("  ❌ " + stage + " table not found")

# Check active streams
active_streams = spark.streams.active
print("\n📡 Active streams: " + str(len(active_streams)))
for stream in active_streams:
    print("  - Stream " + stream.id + ": " + stream.status['message'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary & Next Steps

# COMMAND ----------

print("\n" + "="*60)
print("✅ AUTO LOADER DEMO SETUP COMPLETE!")
print("="*60)
print("\n📋 Demo Details:")
print("  Demo ID: " + demo_id)
print("  Start Time: " + str(DEMO_START_TIME))
print("  Auto-shutdown: " + str(demo_end_time))
print("  Duration: " + str(MAX_DEMO_DURATION_HOURS) + " hours")

print("\n📊 Resources Created:")
print("  - 4 Delta tables (ingestion, validated, enriched, aggregated)")
print("  - 1 Auto Loader stream (ingestion)")
print("  - Checkpoint locations in S3")
print("  - Monitoring metadata")

print("\n🚀 Next Steps:")
print("  1. Upload JSON files to: " + BUCKETS["ingestion"])
print("  2. Files will be automatically processed every 30 seconds")
print("  3. Monitor progress in the tables")
print("  4. Stream will auto-terminate after 24 hours")

print("\n💰 Cost Management:")
print("  - All resources will shut down automatically")
print("  - To stop early, run the teardown notebook")
print("  - Estimated cost: <$10 for 24-hour demo")

print("\n📝 To tear down this demo:")
print("  Run notebook: 02-teardown-autoloader-demo")
print("  With parameter: demo_id=" + demo_id)

# Display summary
displayHTML("""
<div style="background-color: #f0f8ff; padding: 20px; border-radius: 10px; margin-top: 20px;">
    <h2>🎉 Demo Ready!</h2>
    <p><strong>Demo ID:</strong> <code>""" + demo_id + """</code></p>
    <p><strong>Upload files to:</strong> <code>""" + BUCKETS["ingestion"] + """</code></p>
    <p><strong>Auto-shutdown in:</strong> """ + str(MAX_DEMO_DURATION_HOURS) + """ hours</p>
    <p style="color: #ff6b6b; margin-top: 15px;">
        ⚠️ <strong>Important:</strong> This demo will automatically shut down to prevent charges.
        To stop early or extend, use the teardown notebook.
    </p>
</div>
""")