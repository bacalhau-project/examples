# Databricks notebook source
# MAGIC %md
# MAGIC ## Upload Metadata
# MAGIC - **Uploaded:** 2025-08-14 12:31:36
# MAGIC - **Validated:** ✓ (syntax check passed)
# MAGIC - **Source:** setup-and-run-autoloader.py (merged from flexible-autoloader.py)
# MAGIC - **User:** aronchick@gmail.com
# MAGIC - **Host:** M2-Max.local
# MAGIC - **Version:** 1.0.0
# MAGIC - **Description:** Production-ready Auto Loader with 4-stage pipeline
# MAGIC - **Fixed:** Unclosed parenthesis at line 619
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC # Simple Ingestion Pipeline - Production Ready
# MAGIC
# MAGIC Each pipeline ingests from its own bucket to its own table.
# MAGIC All validation, enrichment, and aggregation happens BEFORE data reaches the buckets.

# COMMAND ----------

import json
import time
from datetime import datetime, timedelta

# In Databricks, PySpark is pre-imported but we need to access functions
from pyspark.sql import functions as F

# Configuration
CATALOG = "expanso_databricks_workspace"
SCHEMA = "sensor_readings"
RUNTIME_MINUTES = 60
POLL_INTERVAL_SECONDS = 30  # How often to restart pipelines for new data

# DEBUGGING MODE - Set to True to enable detailed debugging output
DEBUG_MODE = True  # Change to False for production

# ALL FOUR S3 BUCKETS
# Using flat file structure: files are at bucket root as YYYYMMDD_HHMMSS_uniqueid.json
# Pipeline manager mapping: raw→ingestion, schematized→validated, filtered→enriched, aggregated→aggregated
INGESTION_BUCKET = (
    "s3://expanso-databricks-ingestion-us-west-2/"  # receives "raw" pipeline data
)
VALIDATED_BUCKET = "s3://expanso-databricks-validated-us-west-2/"  # receives "schematized" pipeline data
ENRICHED_BUCKET = (
    "s3://expanso-databricks-enriched-us-west-2/"  # receives "filtered" pipeline data
)
AGGREGATED_BUCKET = "s3://expanso-databricks-aggregated-us-west-2/"  # receives "aggregated" pipeline data
CHECKPOINT_BUCKET = "s3://expanso-databricks-checkpoints-us-west-2/"
SCHEMA_BASE = "s3://expanso-databricks-metadata-us-west-2/schemas"  # CRITICAL: Required for Auto Loader!

# ALL FOUR TABLES
INGESTION_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_ingestion"
VALIDATED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_validated"
ENRICHED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_enriched"
AGGREGATED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_aggregated"

print(f"✅ Configuration loaded for ALL FOUR STAGES")
if DEBUG_MODE:
    print(f"🔍 DEBUG MODE ENABLED")
    print(f"   Ingestion: {INGESTION_BUCKET}")
    print(f"   Checkpoint: {CHECKPOINT_BUCKET}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Check Current State (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: CHECKING CURRENT STATE")
    print("=" * 80)

    # Check active queries
    active_queries = spark.streams.active
    print(f"\n📊 Active streaming queries: {len(active_queries)}")

    for i, query in enumerate(active_queries, 1):
        print(f"\nQuery {i}:")
        print(f"  ID: {query.id}")
        print(f"  Name: {query.name if query.name else 'unnamed'}")
        print(f"  Is Active: {query.isActive}")

        if query.lastProgress:
            progress = query.lastProgress
            print(f"  Last Batch ID: {progress.get('batchId', 'N/A')}")
            print(f"  Input Rows: {progress.get('numInputRows', 0)}")

            if "sources" in progress and progress["sources"]:
                source = progress["sources"][0]
                if source.get("startOffset") == source.get("endOffset"):
                    print(f"  ⏸️ Status: WAITING (no new data)")
                else:
                    print(f"  ✅ Status: PROCESSING")

        if query.exception():
            print(f"  ❌ Exception: {query.exception()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Test S3 Access Directly (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: TESTING DIRECT S3 ACCESS")
    print("=" * 80)

    # Test 1: Can we list files with dbutils?
    print("\n1. Testing dbutils.fs.ls:")
    try:
        # List the bucket root (no /raw/ - we use flat structure now)
        files = dbutils.fs.ls("s3://expanso-databricks-ingestion-us-west-2/")
        print(f"   ✅ Found {len(files)} items in bucket root")

        # Show first few files
        json_files = [f for f in files if f.name.endswith(".json")]
        print(f"   ✅ Found {len(json_files)} JSON files")
        for f in json_files[:3]:
            print(f"      - {f.name}")

    except Exception as e:
        print(f"   ❌ Error with dbutils: {str(e)[:200]}")

    # Test 2: Read JSON files directly
    print("\n2. Testing direct JSON read:")
    try:
        # Read all JSON files at bucket root (flat structure)
        test_path = "s3://expanso-databricks-ingestion-us-west-2/*.json"
        df = spark.read.option("multiLine", "true").json(test_path)
        count = df.count()
        print(f"   ✅ Read {count} records from {test_path}")

        # Show schema
        print("   Schema:")
        df.printSchema()

    except Exception as e:
        print(f"   ❌ Error reading JSON: {str(e)[:200]}")

    # Test 3: Try with different path formats
    print("\n3. Testing path variations:")
    paths_to_try = [
        "s3a://expanso-databricks-ingestion-us-west-2/",
        "s3://expanso-databricks-ingestion-us-west-2/",
        "/",
    ]

    for path in paths_to_try:
        try:
            test = spark.read.format("binaryFile").load(path + "*.json")
            print(f"   ✅ {path} - Can access")
        except Exception as e:
            print(f"   ❌ {path} - Cannot access")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Check S3 Files (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: CHECKING S3 FILES")
    print("=" * 80)

    def debug_check_s3(bucket_path, name):
        print(f"\n📁 {name}: {bucket_path}")
        try:
            # Method 1: Try using dbutils.fs.ls
            try:
                files_list = dbutils.fs.ls(bucket_path)
                print(f"  Directories/files at root: {len(files_list)}")
                for f in files_list[:5]:
                    print(f"    - {f.path}")
            except Exception:
                pass

            # Method 2: Try reading with glob pattern
            try:
                # Try to read JSON files with glob (flat structure - no subdirs)
                test_df = spark.read.option("multiLine", "true").json(
                    bucket_path + "*.json"
                )
                test_count = test_df.count()
                print(f"  ✅ Can read {test_count} records from JSON files")

                # Show sample paths
                if test_count > 0:
                    print("  Sample record:")
                    test_df.select("*").limit(1).show(truncate=False)
            except Exception as e2:
                print(f"  ⚠️ Cannot read with glob pattern: {str(e2)[:100]}")

            # Method 3: Try binary file format with recursive
            try:
                files_df = (
                    spark.read.format("binaryFile")
                    .option("recursiveFileLookup", "true")
                    .option("pathGlobFilter", "*.json")
                    .load(bucket_path)
                )
                total_files = files_df.count()

                if total_files > 0:
                    # Count by file type
                    data_files = files_df.filter(
                        F.col("path").endswith("data.json")
                    ).count()
                    metadata_files = files_df.filter(
                        F.col("path").endswith("metadata.json")
                    ).count()

                    print(f"  Total JSON files: {total_files}")
                    print(f"  data.json files: {data_files}")
                    print(f"  metadata.json files: {metadata_files}")

                    # Show sample paths
                    print("  Sample file paths:")
                    files_df.select("path").limit(3).show(truncate=False)
                else:
                    print(f"  ⚠️ No files found with binaryFile format")

            except Exception as e3:
                print(f"  ❌ Error with binaryFile: {str(e3)[:100]}")
        except Exception as e:
            print(f"  ❌ Error with debug_check_s3: {str(e)[:100]}")

    debug_check_s3(INGESTION_BUCKET, "INGESTION")
    if DEBUG_MODE:  # Extra verbose in debug
        debug_check_s3(VALIDATED_BUCKET, "VALIDATED")
        debug_check_s3(ENRICHED_BUCKET, "ENRICHED")
        debug_check_s3(AGGREGATED_BUCKET, "AGGREGATED")

    # Additional test: Try reading flat files
    print("\n📁 FLAT FILE TEST:")
    try:
        # Try reading flat JSON files at bucket root
        test_path = "s3://expanso-databricks-ingestion-us-west-2/*.json"
        direct_df = spark.read.option("multiLine", "true").json(test_path)
        count = direct_df.count()
        print(f"  ✅ Read {count} records from flat files at bucket root")

        # Show sample file names
        files_df = spark.read.format("binaryFile").load(test_path)
        print("  Sample files:")
        files_df.select("path").limit(3).show(truncate=False)
    except Exception as e:
        print(f"  ❌ Cannot read flat files: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Check Checkpoints (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: CHECKING CHECKPOINTS")
    print("=" * 80)

    def debug_checkpoint(checkpoint_path, name):
        print(f"\n🔍 {name} checkpoint: {checkpoint_path}")
        try:
            checkpoint_files = dbutils.fs.ls(checkpoint_path)
            print(f"  ✅ Exists with {len(checkpoint_files)} items")

            # Check offsets
            try:
                offsets = dbutils.fs.ls(f"{checkpoint_path}/offsets/")
                if offsets:
                    latest_offset = max(
                        [int(f.name) for f in offsets if f.name.isdigit()]
                    )
                    print(f"  Latest offset batch: {latest_offset}")

                    # Read offset to see what files were processed
                    offset_content = dbutils.fs.head(
                        f"{checkpoint_path}/offsets/{latest_offset}", max_bytes=500
                    )
                    if "raw/" in offset_content:
                        print(f"  ✅ Processing from /raw/ path")
                    elif "ingestion/" in offset_content:
                        print(f"  ⚠️ Still processing from OLD /ingestion/ path!")
                    print(f"  Offset preview: {offset_content[:100]}...")
            except:
                print("  No offsets found (fresh start)")

        except Exception as e:
            print(f"  ⚠️ Not found (will be created): {str(e)[:100]}")

    debug_checkpoint(CHECKPOINT_BUCKET + "ingestion/checkpoint", "INGESTION")
    debug_checkpoint(CHECKPOINT_BUCKET + "validation/checkpoint", "VALIDATION")
    debug_checkpoint(CHECKPOINT_BUCKET + "enrichment/checkpoint", "ENRICHMENT")
    debug_checkpoint(CHECKPOINT_BUCKET + "aggregation/checkpoint", "AGGREGATION")

# COMMAND ----------

# Create catalog and schema
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Clean Up Existing Tables (Run at start of demo)

# COMMAND ----------

# CLEANUP AT START - Prevents LOCATION_OVERLAP errors
print("=" * 80)
print("🧹 DEMO CLEANUP - STARTING FRESH")
print("=" * 80)

# 1. Drop ALL sensor-related tables from ALL schemas to release S3 locations
print("\n📊 Dropping ALL sensor-related tables from Unity Catalog...")

# Drop tables from our target schema
tables_to_drop = [INGESTION_TABLE, VALIDATED_TABLE, ENRICHED_TABLE, AGGREGATED_TABLE]

for table in tables_to_drop:
    try:
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        print(f"   ✅ Dropped: {table}")
    except Exception as e:
        print(f"   ⚠️  Could not drop {table}: {str(e)[:50]}")

# IMPORTANT: Also drop tables from other schemas that might conflict
# Also drop tables from other schemas that might conflict (wrong schema names)
other_tables_to_drop = [
    # Wrong schema name (sensor_data instead of sensor_readings)
    f"{CATALOG}.sensor_data.sensor_data_ingestion",
    f"{CATALOG}.sensor_data.sensor_data_validated",
    f"{CATALOG}.sensor_data.sensor_data_enriched",
    f"{CATALOG}.sensor_data.sensor_data_aggregated",
    f"{CATALOG}.sensor_data.sensor_readings_ingestion",
    f"{CATALOG}.sensor_data.sensor_readings_validated",
    f"{CATALOG}.sensor_data.sensor_readings_enriched",
    f"{CATALOG}.sensor_data.sensor_readings_aggregated",
]

for table in other_tables_to_drop:
    try:
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        print(f"   ✅ Dropped conflicting: {table}")
    except:
        pass  # Ignore if doesn't exist

# Also check all schemas for any sensor-related tables
try:
    schemas = spark.sql(f"SHOW SCHEMAS IN {CATALOG}").collect()
    for schema_row in schemas:
        schema_name = schema_row["databaseName"]
        try:
            tables = spark.sql(f"SHOW TABLES IN {CATALOG}.{schema_name}").collect()
            for table_row in tables:
                table_name = table_row["tableName"]
                if "sensor" in table_name.lower() or "reading" in table_name.lower():
                    full_name = f"{CATALOG}.{schema_name}.{table_name}"
                    try:
                        spark.sql(f"DROP TABLE IF EXISTS {full_name}")
                        print(f"   ✅ Dropped from {schema_name}: {table_name}")
                    except:
                        pass
        except:
            pass
except Exception as e:
    print(f"   ⚠️  Could not scan all schemas: {str(e)[:100]}")

# 2. Clean S3 buckets to remove all old files
print("\n🪣 Cleaning S3 buckets...")
buckets_to_clean = [
    ("s3://expanso-databricks-ingestion-us-west-2/", "INGESTION"),
    ("s3://expanso-databricks-validated-us-west-2/", "VALIDATED"),
    ("s3://expanso-databricks-enriched-us-west-2/", "ENRICHED"),
    ("s3://expanso-databricks-aggregated-us-west-2/", "AGGREGATED"),
]

for bucket_path, name in buckets_to_clean:
    try:
        # List and remove all files
        files = dbutils.fs.ls(bucket_path)
        if files:
            for item in files:
                dbutils.fs.rm(item.path, recurse=True)
            print(f"   ✅ Cleaned {name}: removed {len(files)} items")
        else:
            print(f"   ✅ {name}: already empty")
    except Exception as e:
        if "FileNotFoundException" in str(e):
            print(f"   ✅ {name}: empty (no files found)")
        else:
            print(f"   ⚠️  {name}: {str(e)[:50]}")

# 3. Clean checkpoint locations
print("\n🔖 Cleaning checkpoints...")
checkpoint_paths = [
    CHECKPOINT_BUCKET + "ingestion/",
    CHECKPOINT_BUCKET + "validation/",
    CHECKPOINT_BUCKET + "enrichment/",
    CHECKPOINT_BUCKET + "aggregation/",
    CHECKPOINT_BUCKET + "test/",  # From test pipelines
]

for checkpoint in checkpoint_paths:
    try:
        dbutils.fs.rm(checkpoint, recurse=True)
        print(f"   ✅ Removed: {checkpoint}")
    except:
        print(f"   ℹ️  No checkpoint at: {checkpoint}")

print("\n" + "=" * 80)
print("✅ CLEANUP COMPLETE - Ready for fresh demo!")
print("   - All Delta tables dropped")
print("   - All S3 buckets cleaned")
print("   - All checkpoints removed")
print("=" * 80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize Buckets with Schema Sample Files

# COMMAND ----------

# Create sample files for schema inference after cleanup
# This ensures Auto Loader can infer schema even when buckets are empty
print("=" * 80)
print("📝 CREATING SCHEMA SAMPLE FILES")
print("=" * 80)
print("Creating one sample file per bucket for Auto Loader schema inference...\n")

from datetime import datetime, timezone
import json

# Create comprehensive sample record with all possible fields
sample_timestamp = datetime.now(timezone.utc)
sample_record = {
    # Core sensor fields
    "id": 1,
    "timestamp": sample_timestamp.isoformat(),
    "sensor_id": "SCHEMA-INIT",
    "temperature": 20.0,
    "humidity": 50.0,
    "pressure": 1013.25,
    "vibration": 0.5,
    "voltage": 12.0,
    "status_code": 0,
    "anomaly_flag": 0,
    "anomaly_type": None,
    # Metadata fields
    "firmware_version": "1.0.0",
    "model": "SchemaModel",
    "manufacturer": "SchemaInit",
    "location": "Schema Initialization",
    "latitude": 0.0,
    "longitude": 0.0,
    "original_timezone": "+00:00",
    "synced": 0,
    "serial_number": "SCHEMA-001",
    "manufacture_date": "2025-01-01",
    "deployment_type": "initialization",
    "installation_date": "2025-01-01",
    "height_meters": 0.0,
    "orientation_degrees": 0.0,
    "instance_id": "schema-instance",
    "sensor_type": "initialization",
    # Validation fields (for validated pipeline)
    "is_valid": True,
    "validation_errors": None,
    "source_format": "initialization",
    # Enrichment fields (for enriched pipeline)
    "data_quality_score": 1.0,
    "alert_level": "normal",
    "sensor_health": "healthy",
    "day_of_week": sample_timestamp.isoweekday(),
    "hour_of_day": sample_timestamp.hour,
    "minute_of_hour": sample_timestamp.minute,
    # Aggregation fields (for aggregated pipeline)
    "window_start": sample_timestamp.isoformat(),
    "window_end": sample_timestamp.isoformat(),
    "record_count": 1,
    "avg_temperature": 20.0,
    "min_temperature": 20.0,
    "max_temperature": 20.0,
    "avg_humidity": 50.0,
    "avg_pressure": 1013.25,
    "avg_voltage": 12.0,
    "avg_vibration": 0.5,
    "max_vibration": 0.5,
    "critical_alerts": 0,
    "warning_alerts": 0,
    "anomaly_count": 0,
    "unhealthy_readings": 0,
    "avg_quality_score": 1.0,
}

# Upload sample to each bucket
buckets_to_init = [
    (INGESTION_BUCKET, "ingestion"),
    (VALIDATED_BUCKET, "validated"),
    (ENRICHED_BUCKET, "enriched"),
    (AGGREGATED_BUCKET, "aggregated"),
]

timestamp_str = sample_timestamp.strftime("%Y%m%d_%H%M%S")

for bucket_path, pipeline_type in buckets_to_init:
    try:
        # Create sample file name
        sample_key = f"schema_sample_{timestamp_str}_{pipeline_type}.json"
        full_path = bucket_path + sample_key

        # Write sample file as JSON array (Auto Loader expects arrays)
        dbutils.fs.put(full_path, json.dumps([sample_record]), overwrite=True)

        print(f"   ✅ {pipeline_type:12} sample created: {sample_key}")

    except Exception as e:
        print(f"   ⚠️  {pipeline_type:12} sample creation failed: {str(e)[:100]}")

print("\n" + "=" * 80)
print("✅ SCHEMA SAMPLES CREATED")
print("   Auto Loader can now infer schema from these files")
print("=" * 80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Test Simple Streaming (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: TESTING SIMPLE STREAMING PIPELINE")
    print("=" * 80)

    try:
        # Create a very simple streaming query
        print("\nCreating simple test stream...")

        test_stream = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", CHECKPOINT_BUCKET + "test/schema")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("multiLine", "true")
            .option("pathGlobFilter", "*.json")
            .load(INGESTION_BUCKET)
        )

        print("✅ Stream reader created")

        # Try to start it - use availableNow trigger for serverless
        # MUST specify checkpoint location - Databricks requires it for ALL streaming queries
        test_query = (
            test_stream.writeStream.format("console")
            .outputMode("append")
            .option("checkpointLocation", CHECKPOINT_BUCKET + "test/debug_console")
            .start()
        )

        print(f"✅ Test query started: {test_query.id}")
        print(f"   Is Active: {test_query.isActive}")

        # Wait a bit
        time.sleep(5)

        # Check status
        if test_query.isActive:
            print("✅ Test stream is running!")
            if test_query.lastProgress:
                print(
                    f"   Progress: {test_query.lastProgress.get('numInputRows', 'N/A')} rows"
                )
        else:
            print("❌ Test stream stopped")
            if test_query.exception():  # Need to call the method with ()
                print(f"   Exception: {test_query.exception()}")

        # Stop the test
        test_query.stop()
        print("✅ Test stream stopped")

    except Exception as e:
        print(f"❌ Test stream failed: {e}")
        import traceback

        traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 1: Raw Ingestion Pipeline

# COMMAND ----------


def create_ingestion_pipeline():
    """Stage 1: Simple ingestion from S3 to Delta table"""

    print("🚀 Starting INGESTION pipeline...")

    if DEBUG_MODE:
        print(f"  📁 Source: {INGESTION_BUCKET}")
        print(f"  📊 Target: {INGESTION_TABLE}")
        print(f"  🔖 Checkpoint: {CHECKPOINT_BUCKET}ingestion/checkpoint")
        print(
            f"  📝 Schema Location: {SCHEMA_BASE}/ingestion"
        )  # CRITICAL for Auto Loader
        print(f"  🔍 Filter: *.json (all JSON files at root level)")

    # Read JSON with schema evolution
    stream_reader = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option(
            "cloudFiles.schemaLocation", f"{SCHEMA_BASE}/ingestion"
        )  # REQUIRED for Auto Loader!
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option(
            "cloudFiles.maxFilesPerTrigger", 10 if DEBUG_MODE else 100
        )  # Smaller batches in debug
        .option("multiLine", "true")
        .option(
            "recursiveFileLookup", "false"
        )  # No need for recursion with flat structure
        .option("cloudFiles.allowOverwrites", "true")
        .option("pathGlobFilter", "*.json")  # Match all JSON files at top level
        .option("cloudFiles.useNotifications", "false")  # Don't use SQS
    )

    if DEBUG_MODE:
        stream_reader = stream_reader.option("cloudFiles.maxBytesPerTrigger", "10MB")

    df = stream_reader.load(INGESTION_BUCKET)

    # Add ingestion metadata
    final_df = df.withColumn("ingestion_timestamp", F.current_timestamp())

    # Write to ingestion table
    writer = (
        final_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_BUCKET + "ingestion/checkpoint")
        .option("mergeSchema", "true")
    )

    # Use availableNow trigger - process all available data then stop
    writer = writer.trigger(availableNow=True)

    if DEBUG_MODE:
        writer = writer.queryName("debug_ingestion")

    query = writer.table(INGESTION_TABLE)

    return query


# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 2: Validated Data Pipeline

# COMMAND ----------


def create_validation_pipeline():
    """Stage 2: Ingest pre-validated data"""

    print("🚀 Starting VALIDATION pipeline...")

    # Read pre-validated JSON
    df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option(
            "cloudFiles.schemaLocation", f"{SCHEMA_BASE}/validated"
        )  # REQUIRED for Auto Loader!
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.maxFilesPerTrigger", 100)
        .option("multiLine", "true")
        .option(
            "recursiveFileLookup", "false"
        )  # No need for recursion with flat structure
        .option("cloudFiles.allowOverwrites", "true")
        .option("pathGlobFilter", "*.json")  # Match all JSON files at top level
        .load(VALIDATED_BUCKET)
    )

    # Add ingestion metadata
    final_df = df.withColumn("ingestion_timestamp", F.current_timestamp())

    # Write to validated table
    query = (
        final_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_BUCKET + "validated/checkpoint")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .table(VALIDATED_TABLE)
    )

    return query


# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 3: Enriched Data Pipeline

# COMMAND ----------


def create_enrichment_pipeline():
    """Stage 3: Ingest pre-enriched data"""

    print("🚀 Starting ENRICHMENT pipeline...")

    # Read pre-enriched JSON
    df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option(
            "cloudFiles.schemaLocation", f"{SCHEMA_BASE}/enriched"
        )  # REQUIRED for Auto Loader!
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.maxFilesPerTrigger", 100)
        .option("multiLine", "true")
        .option(
            "recursiveFileLookup", "false"
        )  # No need for recursion with flat structure
        .option("cloudFiles.allowOverwrites", "true")
        .option("pathGlobFilter", "*.json")  # Match all JSON files at top level
        .load(ENRICHED_BUCKET)
    )

    # Add ingestion metadata
    final_df = df.withColumn("ingestion_timestamp", F.current_timestamp())

    # Write to enriched table
    query = (
        final_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_BUCKET + "enriched/checkpoint")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .table(ENRICHED_TABLE)
    )

    return query


# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 4: Aggregated Data Pipeline

# COMMAND ----------


def create_aggregation_pipeline():
    """Stage 4: Ingest pre-aggregated data"""

    print("🚀 Starting AGGREGATION pipeline...")

    # Read pre-aggregated JSON
    df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option(
            "cloudFiles.schemaLocation", f"{SCHEMA_BASE}/aggregated"
        )  # REQUIRED for Auto Loader!
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.maxFilesPerTrigger", 100)
        .option("multiLine", "true")
        .option(
            "recursiveFileLookup", "false"
        )  # No need for recursion with flat structure
        .option("cloudFiles.allowOverwrites", "true")
        .option("pathGlobFilter", "*.json")  # Match all JSON files at top level
        .load(AGGREGATED_BUCKET)
    )

    # Add ingestion metadata
    final_df = df.withColumn("ingestion_timestamp", F.current_timestamp())

    # Write to aggregated table
    query = (
        final_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_BUCKET + "aggregated/checkpoint")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .table(AGGREGATED_TABLE)
    )

    return query


# COMMAND ----------

# MAGIC %md
# MAGIC ## Start ALL FOUR Pipelines with Complete Setup

# COMMAND ----------

import time
from datetime import datetime

# Configuration
DEBUG_MODE = True  # Set to False to reduce output
SCHEMA_BASE = "s3://expanso-databricks-metadata-us-west-2/schemas"  # CRITICAL: Schema location for Auto Loader

# Stop any existing streaming queries first
print("🛑 STOPPING ANY EXISTING PIPELINES")
print("=" * 60)
for query in spark.streams.active:
    print(f"   Stopping: {query.name if query.name else query.id}")
    query.stop()
    query.awaitTermination(10)
print("✅ All existing pipelines stopped\n")

# Clear checkpoints AND schemas to force reprocessing from beginning
print("🧹 CLEARING CHECKPOINTS AND SCHEMAS FOR FRESH START")
print("=" * 60)
checkpoint_base = "s3://expanso-databricks-checkpoints-us-west-2"
checkpoints_cleared = []
schemas_cleared = []

for pipeline in ["ingestion", "validated", "enriched", "aggregated"]:
    # Clear checkpoints
    checkpoint_path = f"{checkpoint_base}/{pipeline}/checkpoint/"
    try:
        if dbutils.fs.ls(checkpoint_path):
            dbutils.fs.rm(checkpoint_path, recurse=True)
            print(f"  ✅ Cleared {pipeline} checkpoint")
            checkpoints_cleared.append(pipeline)
    except:
        print(f"  ⚠️  No checkpoint found for {pipeline} (this is normal for first run)")

    # Clear schema locations (IMPORTANT for Auto Loader)
    schema_path = f"{SCHEMA_BASE}/{pipeline}/"
    try:
        if dbutils.fs.ls(schema_path):
            dbutils.fs.rm(schema_path, recurse=True)
            print(f"  ✅ Cleared {pipeline} schema")
            schemas_cleared.append(pipeline)
    except:
        print(f"  ⚠️  No schema found for {pipeline} (this is normal for first run)")

if checkpoints_cleared or schemas_cleared:
    print(
        f"\n✅ Cleared {len(checkpoints_cleared)} checkpoint(s) and {len(schemas_cleared)} schema(s)"
    )
else:
    print("\n✅ No existing checkpoints or schemas found - starting fresh")

if DEBUG_MODE:
    print("\n🔍 DEBUG: Waiting 5 seconds to ensure clean state...")
    time.sleep(5)
else:
    time.sleep(2)  # Brief pause even in non-debug mode

print("\n🚀 STARTING ALL FOUR PIPELINES")
print("=" * 60)

# Verify S3 access before starting pipelines
print("🔍 Verifying S3 access...")
try:
    test_files = dbutils.fs.ls("s3://expanso-databricks-ingestion-us-west-2/")
    json_files = [f for f in test_files if f.name.endswith(".json")]
    print(f"  ✅ Found {len(json_files)} JSON files ready to process")

    # Show latest files
    if json_files and DEBUG_MODE:
        recent_files = sorted(json_files, key=lambda x: x.modificationTime)[-5:]
        print("  📁 Recent files:")
        for f in recent_files:
            mod_time = datetime.fromtimestamp(f.modificationTime / 1000).strftime(
                "%H:%M:%S"
            )
            print(f"     - {f.name} ({f.size} bytes, modified {mod_time})")

except Exception as e:
    print(f"  ⚠️  Warning: Could not list S3 files: {str(e)[:100]}")

print()


# COMMAND ----------

# MAGIC %md
# MAGIC ## Start Pipelines with Complete Setup

# COMMAND ----------

# Start all pipelines with proper error handling
pipelines_started = {}

try:
    ingestion_query = create_ingestion_pipeline()
    pipelines_started["INGESTION"] = ingestion_query
    print("✅ Ingestion pipeline started")

    if DEBUG_MODE:
        # Check if query is actually active
        print(f"  📊 Query active: {ingestion_query.isActive}")
        print(f"  📊 Query ID: {ingestion_query.id}")

        # Wait and check initial status
        print("  ⏳ Waiting 10 seconds for initial processing...")
        time.sleep(10)

        # Check again
        print(f"  📊 Still active: {ingestion_query.isActive}")

        if ingestion_query.lastProgress:
            progress = ingestion_query.lastProgress
            print(f"  📊 Initial batch: {progress.get('batchId', 'N/A')}")
            print(f"  📊 Input rows: {progress.get('numInputRows', 0)}")

            # Show source details
            if "sources" in progress and progress["sources"]:
                source = progress["sources"][0]
                print(f"  📊 Files in batch: {source.get('numFiles', 0)}")
        else:
            print("  ⏸️  No progress yet (still initializing)")

        # Check for exceptions
        if ingestion_query.exception():
            print(f"  ❌ Query exception: {ingestion_query.exception()}")

except Exception as e:
    print(f"❌ Ingestion pipeline failed: {e}")
    if DEBUG_MODE:
        import traceback

        traceback.print_exc()

try:
    validation_query = create_validation_pipeline()
    pipelines_started["VALIDATION"] = validation_query
    print("✅ Validation pipeline started")
except Exception as e:
    print(f"❌ Validation pipeline failed: {str(e)[:200]}")

try:
    enrichment_query = create_enrichment_pipeline()
    pipelines_started["ENRICHMENT"] = enrichment_query
    print("✅ Enrichment pipeline started")
except Exception as e:
    print(f"❌ Enrichment pipeline failed: {str(e)[:200]}")

try:
    aggregation_query = create_aggregation_pipeline()
    pipelines_started["AGGREGATION"] = aggregation_query
    print("✅ Aggregation pipeline started")
except Exception as e:
    print(f"❌ Aggregation pipeline failed: {str(e)[:200]}")

print("=" * 60)
print(f"✅ {len(pipelines_started)} PIPELINES RUNNING")

# Show summary
if pipelines_started:
    print("\n📊 PIPELINE SUMMARY:")
    for name, query in pipelines_started.items():
        status = "🟢 Active" if query.isActive else "🔴 Stopped"
        print(f"  {name}: {status} (ID: {query.id[:8]}...)")

print("\n💡 NEXT STEPS:")
print("  1. Run the monitoring cell to track progress")
print("  2. Run the diagnostic cell if pipelines appear stuck")
print("  3. Check the Streaming tab in Databricks for detailed status")

# COMMAND ----------

# CELL: Diagnose Pipeline Issues
# Run this cell to see what's actually happening with the pipelines

import time
from datetime import datetime

print("🔍 PIPELINE DIAGNOSTICS")
print("=" * 60)

# 1. Check active streaming queries
print("\n📊 ACTIVE STREAMING QUERIES:")
print("-" * 40)
active_queries = spark.streams.active
if active_queries:
    for query in active_queries:
        print(f"\n Query ID: {query.id}")
        print(f" Name: {query.name if query.name else 'Unnamed'}")
        print(f" Active: {query.isActive}")
        print(f" Status: {query.status}")

        # Check for exceptions
        if query.exception():
            print(f" ❌ EXCEPTION: {query.exception()}")

        # Check last progress
        if query.lastProgress:
            progress = query.lastProgress
            print(f" Batch ID: {progress.get('batchId', 'N/A')}")
            print(f" Input Rows: {progress.get('numInputRows', 0)}")
            print(f" Processed Rows: {progress.get('processedRowsPerSecond', 0)}")

            # Check sources
            if "sources" in progress and progress["sources"]:
                for source in progress["sources"]:
                    print(f" Source: {source.get('description', 'Unknown')}")
                    print(f"   - Files: {source.get('numFiles', 0)}")
                    print(
                        f"   - Latest Offset: {str(source.get('latestOffset', 'None'))[:100]}"
                    )
        else:
            print(" ⚠️ No progress information available yet")
else:
    print("❌ No active streaming queries found!")

# 2. Check if tables exist and have recent data
print("\n\n📊 TABLE STATUS:")
print("-" * 40)

tables = [
    "expanso_databricks_workspace.sensor_readings.sensor_readings_ingestion",
    "expanso_databricks_workspace.sensor_readings.sensor_readings_validated",
    "expanso_databricks_workspace.sensor_readings.sensor_readings_enriched",
    "expanso_databricks_workspace.sensor_readings.sensor_readings_aggregated",
]

for table in tables:
    try:
        # Count records
        count = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()[0]["cnt"]

        # Get latest timestamp
        latest = spark.sql(f"SELECT MAX(timestamp) as latest FROM {table}").collect()[
            0
        ]["latest"]

        # Check if data is recent (within last 5 minutes)
        if latest:
            latest_dt = datetime.fromisoformat(str(latest).replace("+00:00", ""))
            now = datetime.now()
            minutes_ago = (now - latest_dt).total_seconds() / 60

            status = (
                "🟢 CURRENT"
                if minutes_ago < 5
                else f"🔴 STALE ({int(minutes_ago)} min old)"
            )
        else:
            status = "🔴 NO DATA"

        print(f"\n{table.split('.')[-1]}:")
        print(f"  Records: {count}")
        print(f"  Latest: {latest}")
        print(f"  Status: {status}")

    except Exception as e:
        print(f"\n{table.split('.')[-1]}:")
        print(f"  ❌ Error: {str(e)[:100]}")

# 3. Check S3 for new files
print("\n\n📁 S3 FILE CHECK:")
print("-" * 40)

try:
    # Check ingestion bucket
    s3_path = "s3://expanso-databricks-ingestion-us-west-2/"
    files = dbutils.fs.ls(s3_path)
    json_files = [f for f in files if f.name.endswith(".json")]

    print(f"Total JSON files: {len(json_files)}")

    # Check for recent files (last 5 minutes)
    now_ms = datetime.now().timestamp() * 1000
    recent_files = [
        f for f in json_files if (now_ms - f.modificationTime) < 300000
    ]  # 5 minutes

    print(f"Files added in last 5 min: {len(recent_files)}")

    if recent_files:
        print("\nRecent files:")
        for f in recent_files[:5]:
            mod_time = datetime.fromtimestamp(f.modificationTime / 1000).strftime(
                "%H:%M:%S"
            )
            print(f"  - {f.name} (modified {mod_time})")

    # Try to read a recent file to check format
    if json_files:
        latest_file = sorted(json_files, key=lambda x: x.modificationTime)[-1]
        print(f"\n🔍 Checking latest file: {latest_file.name}")

        try:
            # Read the file
            df = spark.read.option("multiLine", "true").json(latest_file.path)
            print(f"  ✅ File is valid JSON")
            print(f"  Records: {df.count()}")
            print(f"  Schema fields: {', '.join(df.columns[:10])}")

            # Show sample record
            if df.count() > 0:
                sample = df.first()
                print(
                    f"  Sample sensor_id: {sample.sensor_id if 'sensor_id' in df.columns else 'N/A'}"
                )

        except Exception as e:
            print(f"  ❌ Error reading file: {str(e)[:200]}")

            # Try to show raw content
            try:
                raw_df = spark.read.text(latest_file.path)
                first_line = raw_df.first()[0]
                print(f"  Raw content (first 200 chars): {first_line[:200]}")
            except:
                pass

except Exception as e:
    print(f"❌ Error checking S3: {str(e)[:200]}")

# 4. Check checkpoint locations
print("\n\n🔖 CHECKPOINT STATUS:")
print("-" * 40)

checkpoint_base = "s3://expanso-databricks-checkpoints-us-west-2"
for pipeline in ["ingestion", "validated", "enriched", "aggregated"]:
    checkpoint_path = f"{checkpoint_base}/{pipeline}/checkpoint/"
    try:
        files = dbutils.fs.ls(checkpoint_path)
        if files:
            # Look for offsets directory
            offset_files = [f for f in files if "offsets" in f.path]
            commit_files = [f for f in files if "commits" in f.path]

            print(f"\n{pipeline}:")
            print(f"  Checkpoint exists: ✅")
            print(f"  Offset files: {len(offset_files)}")
            print(f"  Commit files: {len(commit_files)}")

            # Check latest offset
            if offset_files:
                try:
                    offset_dir = offset_files[0].path
                    offset_contents = dbutils.fs.ls(offset_dir)
                    if offset_contents:
                        latest_offset = sorted(offset_contents, key=lambda x: x.name)[
                            -1
                        ]
                        print(f"  Latest offset: {latest_offset.name}")
                except:
                    pass
        else:
            print(f"\n{pipeline}:")
            print(f"  Checkpoint exists: ❌ (Empty)")

    except:
        print(f"\n{pipeline}:")
        print(f"  Checkpoint exists: ❌ (Not found)")

# 5. Recommendations
print("\n\n💡 RECOMMENDATIONS:")
print("-" * 40)

issues = []

# Check for common problems
if not active_queries:
    issues.append("No active streaming queries - pipelines are not running")
    issues.append("ACTION: Re-run the 'Start All Pipelines' cell")

if len(json_files) > 100:
    issues.append(f"Large backlog of {len(json_files)} files in S3")
    issues.append("ACTION: Files are accumulating but not being processed")

# Check if ingestion is stuck
ingestion_queries = [q for q in active_queries if "ingestion" in str(q.status).lower()]
if ingestion_queries and ingestion_queries[0].lastProgress:
    if ingestion_queries[0].lastProgress.get("numInputRows", 0) == 0:
        issues.append("Ingestion pipeline is running but not processing files")
        issues.append("ACTION: Check file format or permissions")

if not issues:
    print("✅ Pipelines appear to be configured correctly")
    print("   If data is not flowing, check the Databricks Streaming tab for errors")
else:
    for issue in issues:
        if issue.startswith("ACTION:"):
            print(f"  → {issue}")
        else:
            print(f"❌ {issue}")

print("\n" + "=" * 60)
print("Diagnostics complete. Check the Streaming tab for more details.")


# COMMAND ----------

# CELL: Complete Reset and Restart
# This cell does a complete reset - use when pipelines are stuck

import time
# PySpark functions are pre-imported in Databricks

print("🔄 COMPLETE PIPELINE RESET")
print("=" * 60)

# 1. Force stop all streams
print("\n1️⃣ FORCE STOPPING ALL STREAMS...")
for query in spark.streams.active:
    print(f"   Stopping: {query.id}")
    query.stop()

# Wait for cleanup
time.sleep(5)

# 2. Clear ALL checkpoints
print("\n2️⃣ CLEARING ALL CHECKPOINTS...")
checkpoint_base = "s3://expanso-databricks-checkpoints-us-west-2"

for pipeline in ["ingestion", "validated", "enriched", "aggregated"]:
    checkpoint_path = f"{checkpoint_base}/{pipeline}/"
    try:
        dbutils.fs.rm(checkpoint_path, recurse=True)
        print(f"   ✅ Cleared {pipeline}")
    except:
        print(f"   ⚠️  {pipeline} already clear")

# 3. Verify S3 access
print("\n3️⃣ VERIFYING S3 ACCESS...")
try:
    s3_path = "s3://expanso-databricks-ingestion-us-west-2/"
    files = dbutils.fs.ls(s3_path)
    json_files = [f for f in files if f.name.endswith(".json")]
    print(f"   ✅ Found {len(json_files)} JSON files in S3")

    # Test read one file
    if json_files:
        test_file = json_files[-1]
        test_df = spark.read.option("multiLine", "true").json(test_file.path)
        print(f"   ✅ Successfully read test file: {test_file.name}")
        print(f"   ✅ Records in file: {test_df.count()}")
except Exception as e:
    print(f"   ❌ S3 Error: {e}")
    raise

# 4. Start ONLY the ingestion pipeline first
print("\n4️⃣ STARTING INGESTION PIPELINE ONLY...")
print("   (We'll start others after confirming ingestion works)")

try:
    # Simple ingestion with minimal options
    ingestion_df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", f"{SCHEMA_BASE}/ingestion")  # REQUIRED!
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.maxFilesPerTrigger", 10)  # Start small
        .option("multiLine", "true")
        .load(s3_path)
    )

    # Add timestamp
    processed_df = ingestion_df.withColumn("processing_time", F.current_timestamp())

    # Write to table
    ingestion_query = (
        processed_df.writeStream.outputMode("append")
        .format("delta")
        .option("checkpointLocation", f"{checkpoint_base}/ingestion/checkpoint")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)  # serverless compatible
        .table("expanso_databricks_workspace.sensor_readings.sensor_readings_ingestion")
    )

    print(f"   ✅ Ingestion started: {ingestion_query.id}")

    print(f"\n   ⏳ Waiting 15 seconds for first batch...")
    time.sleep(15)

    # Check if still running
    if not ingestion_query.isActive:
        print(f"   ❌ Pipeline stopped immediately")
        if ingestion_query.exception():
            print(f"   ❌ Error: {ingestion_query.exception()}")
        if ingestion_query.lastProgress:
            print(
                f"   📊 Last progress: {ingestion_query.lastProgress.get('numInputRows', 0)} rows processed"
            )
        if ingestion_query.exception():
            print(f"   Error: {ingestion_query.exception()}")

except Exception as e:
    print(f"\n❌ Failed to start ingestion: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("Reset complete. Check the Streaming tab for pipeline status.")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor ALL Running Pipelines

# COMMAND ----------


def monitor_pipelines(duration_minutes=60):
    """Monitor all running pipelines"""

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_minutes)

    print(f"🕐 Monitoring {len(pipelines_started)} pipelines until: {end_time}")
    print("=" * 60)

    tables = {
        "INGESTION": INGESTION_TABLE,
        "VALIDATION": VALIDATED_TABLE,
        "ENRICHMENT": ENRICHED_TABLE,
        "AGGREGATION": AGGREGATED_TABLE,
    }

    batch_num = 0
    last_debug_check = 0

    while datetime.now() < end_time:
        batch_num += 1
        print(f"\n📦 Batch #{batch_num} - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)

        # Check each pipeline
        for name in ["INGESTION", "VALIDATION", "ENRICHMENT", "AGGREGATION"]:
            try:
                if name in pipelines_started:
                    query = pipelines_started[name]
                    status = query.status

                    # Get record count
                    count = spark.sql(
                        f"SELECT COUNT(*) as cnt FROM {tables[name]}"
                    ).collect()[0]["cnt"]

                    if status["isDataAvailable"]:
                        progress = query.lastProgress
                        if (
                            progress
                            and "numInputRows" in progress
                            and progress["numInputRows"] > 0
                        ):
                            print(
                                f"   {name}: ✅ {count:,} records (+{progress['numInputRows']} new)"
                            )
                        else:
                            print(f"   {name}: ✅ {count:,} records")
                    else:
                        print(f"   {name}: ⏸️  {count:,} records (waiting)")

                        # In debug mode, show why it's waiting
                        if DEBUG_MODE and name == "INGESTION":
                            if query.lastProgress:
                                progress = query.lastProgress
                                if "sources" in progress and progress["sources"]:
                                    source = progress["sources"][0]
                                    if source.get("startOffset") == source.get(
                                        "endOffset"
                                    ):
                                        print(f"        └─ No new files detected")
                                    else:
                                        print(
                                            f"        └─ Processing offset: {source.get('endOffset', 'N/A')[:50]}..."
                                        )

                            # Check for exceptions
                            if query.exception():
                                print(f"        └─ ❌ Exception: {query.exception()}")
                else:
                    print(f"   {name}: ❌ Not started")

            except Exception as e:
                print(f"   {name}: ⚠️ Error - {str(e)[:50]}")

        # Show data flow summary
        print("\n   📊 Pipeline Flow:")
        for name, table in tables.items():
            try:
                count = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()[0][
                    "cnt"
                ]
                print(f"      {name}: {count:,} records")
            except:
                print(f"      {name}: 0 records")

        remaining = int((end_time - datetime.now()).total_seconds() / 60)
        print(f"\n   ⏱️  Time remaining: {remaining} minutes")

        # Debug: Every 5th batch, do a deeper check
        if DEBUG_MODE and batch_num % 5 == 0:
            print("\n   🔍 DEBUG: Deep Check")
            print("   " + "-" * 35)

            # Check if files are being detected
            try:
                files_df = spark.read.format("binaryFile").load(INGESTION_BUCKET)
                recent_files = files_df.filter(
                    F.col("modificationTime") > datetime.now() - timedelta(minutes=10)
                ).count()
                print(f"   Files modified in last 10 min: {recent_files}")
            except:
                pass

            # Check ingestion query details
            if "INGESTION" in pipelines_started:
                query = pipelines_started["INGESTION"]
                if query.lastProgress:
                    progress = query.lastProgress
                    print(
                        f"   Batch Duration: {progress.get('durationMs', {}).get('triggerExecution', 'N/A')} ms"
                    )
                    state_operators = progress.get("stateOperators", [])
                    if state_operators:
                        print(
                            f"   State: {state_operators[0].get('customMetrics', {})}"
                        )

        time.sleep(15)

    print("\n" + "=" * 60)
    print("⏹️  Stopping all pipelines...")

    # Stop all running pipelines
    for name, query in pipelines_started.items():
        try:
            query.stop()
            print(f"   ✅ {name} stopped")
        except:
            print(f"   ⚠️ {name} already stopped")

    # Final summary
    print("\n📊 FINAL SUMMARY - ALL FOUR STAGES:")
    print("-" * 40)
    for name, table in tables.items():
        try:
            count = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()[0][
                "cnt"
            ]
            print(f"   {name}: {count:,} records")
        except:
            print(f"   {name}: No data")


# Monitor the pipelines
monitor_pipelines(RUNTIME_MINUTES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Diagnose Pipeline Issues (Only runs if DEBUG_MODE = True)

# COMMAND ----------

if DEBUG_MODE:
    print("=" * 80)
    print("DEBUG: PIPELINE DIAGNOSTICS")
    print("=" * 80)

    print("\n🔍 Checking why pipelines might be stuck in 'waiting' state:\n")

    # 1. Check if checkpoints are stale
    print("1. CHECKPOINT STATUS:")
    try:
        ingestion_checkpoint = CHECKPOINT_BUCKET + "ingestion/checkpoint/offsets/"
        offsets = dbutils.fs.ls(ingestion_checkpoint)
        if offsets:
            latest_offset = max([int(f.name) for f in offsets if f.name.isdigit()])
            offset_content = dbutils.fs.head(
                f"{ingestion_checkpoint}{latest_offset}", max_bytes=200
            )

            if "/raw/" in offset_content:
                print("   ✅ Checkpoint is reading from correct /raw/ path")
            elif "/ingestion/" in offset_content:
                print("   ❌ PROBLEM: Checkpoint still has old /ingestion/ path!")
                print(
                    "   FIX: Clear checkpoint by uncommenting and running the cell below"
                )
            else:
                print(f"   ℹ️ Checkpoint content: {offset_content[:100]}")
    except Exception as e:
        print(f"   ℹ️ No checkpoint found (fresh start): {str(e)[:100]}")

    # 2. Check file accessibility
    print("\n2. FILE ACCESSIBILITY:")
    try:
        test_read = spark.read.option("multiLine", "true").json(
            INGESTION_BUCKET + "**/data.json"
        )
        test_count = test_read.count()
        print(f"   ✅ Can read {test_count} files from S3")

        # Check for recent files
        files_df = spark.read.format("binaryFile").load(INGESTION_BUCKET)
        recent = files_df.filter(
            F.col("modificationTime") > datetime.now() - timedelta(hours=1)
        ).count()
        print(f"   ℹ️ Files modified in last hour: {recent}")

    except Exception as e:
        print(f"   ❌ PROBLEM: Cannot read files: {str(e)[:200]}")
        print("   FIX: Check S3 permissions and bucket access")

    # 3. Check for active queries
    print("\n3. ACTIVE QUERIES:")
    active = spark.streams.active
    if not active:
        print("   ❌ PROBLEM: No active streaming queries!")
        print("   FIX: Re-run the pipeline start cell above")
    else:
        for q in active:
            print(f"   ✅ Query '{q.name if q.name else q.id}' is active")
            if q.exception:
                print(f"      ❌ Has exception: {q.exception}")

    # 4. Suggested fixes
    print("\n📝 SUGGESTED FIXES:")
    print("   1. If checkpoint has old path: Clear checkpoints (see cell below)")
    print("   2. If no active queries: Re-run the pipeline start cell")
    print("   3. If permission issues: Check Databricks S3 access configuration")
    print("   4. If still stuck: Set DEBUG_MODE = True and re-run entire notebook")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Debug: Clear Checkpoints (DESTRUCTIVE - Only if needed)

# COMMAND ----------

# UNCOMMENT THESE LINES ONLY IF YOU NEED TO CLEAR CHECKPOINTS
# This will cause all files to be reprocessed from the beginning

# if DEBUG_MODE:
#     print("⚠️ CLEARING ALL CHECKPOINTS - THIS WILL REPROCESS ALL FILES")
#     print("=" * 80)
#
#     def clear_checkpoint(checkpoint_path, name):
#         print(f"Clearing {name} checkpoint: {checkpoint_path}")
#         try:
#             dbutils.fs.rm(checkpoint_path, recurse=True)
#             print(f"  ✅ Cleared successfully")
#         except Exception as e:
#             print(f"  ℹ️ Nothing to clear: {str(e)[:100]}")
#
#     clear_checkpoint(CHECKPOINT_BUCKET + "ingestion/checkpoint", "INGESTION")
#     clear_checkpoint(CHECKPOINT_BUCKET + "validation/checkpoint", "VALIDATION")
#     clear_checkpoint(CHECKPOINT_BUCKET + "enrichment/checkpoint", "ENRICHMENT")
#     clear_checkpoint(CHECKPOINT_BUCKET + "aggregation/checkpoint", "AGGREGATION")
#
#     print("\n✅ All checkpoints cleared. Re-run the pipeline start cell above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Manual Clean All Buckets (Run this to reset demo)
# MAGIC Note: Cleanup also runs automatically at the start of the notebook

# COMMAND ----------

# MANUAL CLEANUP CELL - Removes all files from all buckets for a fresh demo
# This is the same as the automatic cleanup at the start, but can be run manually
if True:  # Always enabled for manual cleanup
    print("=" * 80)
    print("CLEANING ALL BUCKETS FOR FRESH DEMO")
    print("=" * 80)

    buckets_to_clean = [
        ("s3://expanso-databricks-ingestion-us-west-2/", "INGESTION"),
        ("s3://expanso-databricks-validated-us-west-2/", "VALIDATED"),
        ("s3://expanso-databricks-enriched-us-west-2/", "ENRICHED"),
        ("s3://expanso-databricks-aggregated-us-west-2/", "AGGREGATED"),
        ("s3://expanso-databricks-checkpoints-us-west-2/", "CHECKPOINTS"),
    ]

    for bucket_path, name in buckets_to_clean:
        print(f"\n🧹 Cleaning {name} bucket: {bucket_path}")
        try:
            # List all files
            files = dbutils.fs.ls(bucket_path)
            file_count = len(files)

            if file_count == 0:
                print(f"   ✅ Already empty")
                continue

            print(f"   Found {file_count} items to remove")

            # Remove everything recursively
            for item in files:
                try:
                    if item.isDir():
                        # Remove directory recursively
                        dbutils.fs.rm(item.path, recurse=True)
                        print(f"   📁 Removed directory: {item.name}")
                    else:
                        # Remove file
                        dbutils.fs.rm(item.path, recurse=False)
                        print(f"   📄 Removed file: {item.name}")
                except Exception as e:
                    print(f"   ⚠️ Could not remove {item.name}: {str(e)[:100]}")

            print(f"   ✅ {name} bucket cleaned")

        except Exception as e:
            print(f"   ❌ Error cleaning {name}: {str(e)[:200]}")

    # Also clean Delta tables
    print("\n🧹 Cleaning Delta tables...")
    tables_to_clean = [
        INGESTION_TABLE,
        VALIDATED_TABLE,
        ENRICHED_TABLE,
        AGGREGATED_TABLE,
    ]

    for table in tables_to_clean:
        try:
            spark.sql(f"TRUNCATE TABLE {table}")
            print(f"   ✅ Truncated {table}")
        except:
            try:
                spark.sql(f"DROP TABLE IF EXISTS {table}")
                print(f"   ✅ Dropped {table}")
            except Exception as e:
                print(f"   ⚠️ Could not clean {table}: {str(e)[:100]}")

    print("\n" + "=" * 80)
    print("✅ ALL BUCKETS AND TABLES CLEANED - READY FOR FRESH DEMO")
    print("=" * 80)
else:
    print("⚠️ Set DEBUG_MODE = True to enable bucket cleaning")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query Final Results

# COMMAND ----------

# Show pipeline flow
display(
    spark.sql(f"""
    SELECT 
        'Ingestion' as Stage, 
        COUNT(*) as Records,
        MIN(ingestion_timestamp) as Earliest,
        MAX(ingestion_timestamp) as Latest
    FROM {INGESTION_TABLE}
    UNION ALL
    SELECT 'Validation', COUNT(*), MIN(ingestion_timestamp), MAX(ingestion_timestamp) FROM {VALIDATED_TABLE}
    UNION ALL
    SELECT 'Enrichment', COUNT(*), MIN(ingestion_timestamp), MAX(ingestion_timestamp) FROM {ENRICHED_TABLE}
    UNION ALL
    SELECT 'Aggregation', COUNT(*), MIN(ingestion_timestamp), MAX(ingestion_timestamp) FROM {AGGREGATED_TABLE}
    ORDER BY 
        CASE Stage 
            WHEN 'Ingestion' THEN 1
            WHEN 'Validation' THEN 2
            WHEN 'Enrichment' THEN 3
            WHEN 'Aggregation' THEN 4
        END
""")
)

# COMMAND ----------

# Show sample data from each table
for table_name, table_path in [
    ("INGESTION", INGESTION_TABLE),
    ("VALIDATION", VALIDATED_TABLE),
    ("ENRICHMENT", ENRICHED_TABLE),
    ("AGGREGATION", AGGREGATED_TABLE),
]:
    print(f"\n📊 Sample data from {table_name} table:")
    display(
        spark.sql(f"""
        SELECT * FROM {table_path}
        ORDER BY ingestion_timestamp DESC
        LIMIT 5
        """)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Complete 4-Stage Pipeline Running
# MAGIC
# MAGIC All four stages are now simple ingestion pipelines:
# MAGIC 1. **Ingestion** - Reads raw data from S3 ingestion bucket
# MAGIC 2. **Validation** - Reads pre-validated data from S3 validated bucket
# MAGIC 3. **Enrichment** - Reads pre-enriched data from S3 enriched bucket
# MAGIC 4. **Aggregation** - Reads pre-aggregated data from S3 aggregated bucket
# MAGIC
# MAGIC Each pipeline is independent and only handles ingestion from its bucket to its table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Polling-Based Pipeline Runner (Serverless Compatible)
# MAGIC
# MAGIC This cell runs pipelines in a polling loop, restarting them every POLL_INTERVAL_SECONDS.
# MAGIC Each pipeline processes all available data then stops (availableNow trigger).
# MAGIC We monitor progress by tracking table row counts.

# COMMAND ----------

import time
from datetime import datetime, timedelta

# Configuration
POLL_INTERVAL_SECONDS = 30  # How often to restart pipelines
RUNTIME_MINUTES = 60  # Total runtime


def get_table_count(table_name):
    """Get row count for a table."""
    try:
        return spark.table(table_name).count()
    except:
        return 0


def run_pipeline_once(pipeline_func, pipeline_name):
    """Run a pipeline once with availableNow trigger."""
    try:
        query = pipeline_func()
        # Wait for it to complete (availableNow processes then stops)
        while query.isActive:
            time.sleep(1)

        # Check if it succeeded
        if query.exception():
            print(f"  ❌ {pipeline_name} failed: {query.exception()}")
            return False
        else:
            print(f"  ✅ {pipeline_name} completed batch")
            return True
    except Exception as e:
        print(f"  ❌ {pipeline_name} error: {str(e)[:100]}")
        return False


def run_polling_pipelines():
    """Run all pipelines in a polling loop."""

    print("🚀 STARTING POLLING-BASED PIPELINE RUNNER")
    print(f"   Poll Interval: {POLL_INTERVAL_SECONDS} seconds")
    print(f"   Runtime: {RUNTIME_MINUTES} minutes")
    print("=" * 60)

    # Track initial counts
    initial_counts = {
        "ingestion": get_table_count(INGESTION_TABLE),
        "validated": get_table_count(VALIDATED_TABLE),
        "enriched": get_table_count(ENRICHED_TABLE),
        "aggregated": get_table_count(AGGREGATED_TABLE),
    }

    print("\n📊 Initial Table Counts:")
    for table, count in initial_counts.items():
        print(f"   {table}: {count:,} rows")

    # Run for specified duration
    end_time = datetime.now() + timedelta(minutes=RUNTIME_MINUTES)
    iteration = 0

    while datetime.now() < end_time:
        iteration += 1
        print(f"\n🔄 Iteration #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)

        # Run each pipeline
        pipelines = [
            (create_ingestion_pipeline, "Ingestion", INGESTION_TABLE),
            (create_validation_pipeline, "Validation", VALIDATED_TABLE),
            (create_enrichment_pipeline, "Enrichment", ENRICHED_TABLE),
            (create_aggregation_pipeline, "Aggregation", AGGREGATED_TABLE),
        ]

        for func, name, table in pipelines:
            print(f"\n  Running {name}...")
            success = run_pipeline_once(func, name)

            if success:
                current_count = get_table_count(table)
                initial = initial_counts[name.lower()]
                new_rows = current_count - initial
                print(f"    📈 Total: {current_count:,} rows (+{new_rows:,} new)")

        # Check S3 for new files
        try:
            file_count = len(dbutils.fs.ls(INGESTION_BUCKET))
            print(f"\n  📁 Files in S3: {file_count}")
        except:
            pass

        # Update current counts
        print("\n  📊 Current Progress:")
        for name in ["ingestion", "validated", "enriched", "aggregated"]:
            table = globals()[f"{name.upper()}_TABLE"]
            current = get_table_count(table)
            initial = initial_counts[name]
            change = current - initial
            if change > 0:
                print(f"     {name}: +{change:,} rows")

        # Calculate time remaining
        time_remaining = (end_time - datetime.now()).total_seconds() / 60
        print(f"\n  ⏱️  Time remaining: {time_remaining:.1f} minutes")

        # Wait for next poll
        if datetime.now() < end_time:
            print(f"\n  💤 Waiting {POLL_INTERVAL_SECONDS} seconds until next poll...")
            time.sleep(POLL_INTERVAL_SECONDS)

    print("\n" + "=" * 60)
    print("✅ POLLING COMPLETE")

    # Final summary
    print("\n📊 FINAL SUMMARY:")
    for name in ["ingestion", "validated", "enriched", "aggregated"]:
        table = globals()[f"{name.upper()}_TABLE"]
        final_count = get_table_count(table)
        initial = initial_counts[name]
        total_new = final_count - initial
        print(f"   {name}: {final_count:,} total rows (+{total_new:,} new)")


# Run the polling pipeline
run_polling_pipelines()


# COMMAND ----------

# MAGIC %md
# MAGIC ## Simple 4-Bucket Auto Loader Polling
# MAGIC
# MAGIC This cell runs 4 independent Auto Loader pipelines:
# MAGIC - **Ingestion Bucket → Ingestion Table**
# MAGIC - **Validated Bucket → Validated Table**
# MAGIC - **Enriched Bucket → Enriched Table**
# MAGIC - **Aggregated Bucket → Aggregated Table**
# MAGIC
# MAGIC Each pipeline:
# MAGIC 1. Processes all available files in its bucket
# MAGIC 2. Stops when complete (availableNow trigger)
# MAGIC 3. Gets restarted every POLL_INTERVAL_SECONDS

# COMMAND ----------

import time
from datetime import datetime, timedelta

# Clear any existing streams
for s in spark.streams.active:
    s.stop()

print("🚀 STARTING 4-BUCKET AUTO LOADER POLLING")
print("=" * 60)
print(f"📁 Buckets:")
print(f"   Ingestion:  {INGESTION_BUCKET}")
print(f"   Validated:  {VALIDATED_BUCKET}")
print(f"   Enriched:   {ENRICHED_BUCKET}")
print(f"   Aggregated: {AGGREGATED_BUCKET}")
print(f"\\n⏱️  Poll Interval: {POLL_INTERVAL_SECONDS} seconds")
print(f"⏱️  Total Runtime: {RUNTIME_MINUTES} minutes")
print("=" * 60)

end_time = datetime.now() + timedelta(minutes=RUNTIME_MINUTES)
iteration = 0

while datetime.now() < end_time:
    iteration += 1
    remaining = int((end_time - datetime.now()).total_seconds() / 60)

    print(
        f"\\n🔄 Poll #{iteration} at {datetime.now().strftime('%H:%M:%S')} ({remaining} min remaining)"
    )
    print("-" * 40)

    # Start all 4 pipelines
    queries = []

    # 1. INGESTION PIPELINE
    try:
        print("  Starting INGESTION pipeline...")
        q = create_ingestion_pipeline()
        queries.append((q, "INGESTION", INGESTION_TABLE))
        print(f"    ✅ Started (ID: {q.id[:8]}...)")
    except Exception as e:
        print(f"    ❌ Failed: {str(e)[:50]}")

    # 2. VALIDATION PIPELINE
    try:
        print("  Starting VALIDATION pipeline...")
        q = create_validation_pipeline()
        queries.append((q, "VALIDATION", VALIDATED_TABLE))
        print(f"    ✅ Started (ID: {q.id[:8]}...)")
    except Exception as e:
        print(f"    ❌ Failed: {str(e)[:50]}")

    # 3. ENRICHMENT PIPELINE
    try:
        print("  Starting ENRICHMENT pipeline...")
        q = create_enrichment_pipeline()
        queries.append((q, "ENRICHMENT", ENRICHED_TABLE))
        print(f"    ✅ Started (ID: {q.id[:8]}...)")
    except Exception as e:
        print(f"    ❌ Failed: {str(e)[:50]}")

    # 4. AGGREGATION PIPELINE
    try:
        print("  Starting AGGREGATION pipeline...")
        q = create_aggregation_pipeline()
        queries.append((q, "AGGREGATION", AGGREGATED_TABLE))
        print(f"    ✅ Started (ID: {q.id[:8]}...)")
    except Exception as e:
        print(f"    ❌ Failed: {str(e)[:50]}")

    # Wait for all to complete
    print("\\n  ⏳ Waiting for pipelines to complete...")
    for query, name, table in queries:
        while query.isActive:
            time.sleep(1)

        # Get row count
        try:
            count = spark.table(table).count()
            print(f"    {name}: {count:,} total rows")
        except:
            print(f"    {name}: Unable to count")

    # Wait before next poll
    if datetime.now() < end_time:
        print(f"\\n  💤 Sleeping {POLL_INTERVAL_SECONDS} seconds...")
        time.sleep(POLL_INTERVAL_SECONDS)

print("\\n" + "=" * 60)
print("✅ POLLING COMPLETE")
