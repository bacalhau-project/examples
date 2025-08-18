# Databricks notebook source
# MAGIC %md
# MAGIC # Simple Auto Loader Polling Pipeline
# MAGIC
# MAGIC This notebook runs 5 independent Auto Loader pipelines that continuously ingest data from S3 buckets to Unity Catalog tables.
# MAGIC
# MAGIC **Architecture:**
# MAGIC - 5 S3 buckets (ingestion, validated, anomalies, enriched, aggregated) receive data from external service
# MAGIC - 5 Auto Loader pipelines read from these buckets
# MAGIC - Data is written to 5 corresponding Unity Catalog tables
# MAGIC - Pipelines restart every 30 seconds to process new files

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

from pyspark.sql import functions as F
import time
import random
import concurrent.futures
from datetime import datetime, timedelta

# Catalog and Schema
CATALOG = "expanso_databricks_workspace"
SCHEMA = "sensor_readings"

# S3 Buckets (source)
BUCKETS = {
    "ingestion": "s3://expanso-raw-data-us-west-2/",
    "validated": "s3://expanso-validated-data-us-west-2/",
    "anomalies": "s3://expanso-anomalies-data-us-west-2/",
    "enriched": "s3://expanso-schematized-data-us-west-2/",
    "aggregated": "s3://expanso-aggregated-data-us-west-2/",
}

# Unity Catalog Tables (destination)
TABLES = {
    "ingestion": f"{CATALOG}.{SCHEMA}.sensor_readings_ingestion",
    "validated": f"{CATALOG}.{SCHEMA}.sensor_readings_validated",
    "anomalies": f"{CATALOG}.{SCHEMA}.sensor_readings_anomalies",
    "enriched": f"{CATALOG}.{SCHEMA}.sensor_readings_enriched",
    "aggregated": f"{CATALOG}.{SCHEMA}.sensor_readings_aggregated",
}

# Checkpoint and Schema Locations
CHECKPOINT_BASE = "s3://expanso-checkpoints-us-west-2"
SCHEMA_BASE = "s3://expanso-metadata-us-west-2/schemas"

# Polling Configuration
POLL_INTERVAL_SECONDS = 30  # How often to restart pipelines
RUNTIME_MINUTES = 60  # Total runtime

print("✅ Configuration loaded")
print(f"📊 Tables: {', '.join(TABLES.keys())}")
print(f"⏱️  Poll every {POLL_INTERVAL_SECONDS} seconds for {RUNTIME_MINUTES} minutes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test Bucket Access & Clear Buckets

# COMMAND ----------


def test_bucket_access():
    """Test read access to all S3 buckets."""
    print("🔍 Testing S3 Bucket Access")
    print("=" * 40)

    for stage, bucket in BUCKETS.items():
        try:
            files = dbutils.fs.ls(bucket)
            json_files = [f for f in files if f.name.endswith(".json")]
            print(f"✅ {stage:12} : {len(json_files)} JSON files found")
        except Exception as e:
            print(f"❌ {stage:12} : {str(e)[:50]}")
    print()


def upload_schema_samples():
    """Upload sample schema files to each bucket for Auto Loader schema inference."""
    print("📤 Uploading Schema Sample Files")
    print("=" * 40)

    from datetime import datetime
    import json

    # Sample schemas for each stage
    samples = {
        "ingestion": [
            {
                "id": 1,
                "timestamp": datetime.now().isoformat(),
                "sensor_id": "SCHEMA_SAMPLE",
                "temperature": 22.0,
                "humidity": 60.0,
                "pressure": 101325.0,
                "vibration": 0.5,
                "voltage": 24.0,
                "status_code": 0,
                "anomaly_flag": 0,
                "firmware_version": "1.0.0",
                "model": "SampleModel",
                "manufacturer": "SampleMfg",
                "location": "Sample Location",
                "latitude": 0.0,
                "longitude": 0.0,
                "original_timezone": "+00:00",
                "synced": 0,
            }
        ],
        "validated": [
            {
                "id": 1,
                "timestamp": datetime.now().isoformat(),
                "sensor_id": "SCHEMA_SAMPLE",
                "temperature": 22.0,
                "humidity": 60.0,
                "pressure": 101325.0,
                "vibration": 0.5,
                "voltage": 24.0,
                "status_code": 0,
                "anomaly_flag": 0,
                "anomaly_type": None,
                "firmware_version": "1.0.0",
                "model": "SampleModel",
                "manufacturer": "SampleMfg",
                "location": "Sample Location",
                "latitude": 0.0,
                "longitude": 0.0,
                "original_timezone": "+00:00",
                "synced": 0,
                "validation_status": "valid",
            }
        ],
        "enriched": [
            {
                "id": 1,
                "timestamp": datetime.now().isoformat(),
                "sensor_id": "SCHEMA_SAMPLE",
                "temperature": 22.0,
                "humidity": 60.0,
                "pressure": 101325.0,
                "vibration": 0.5,
                "voltage": 24.0,
                "status_code": 0,
                "anomaly_flag": 0,
                "firmware_version": "1.0.0",
                "model": "SampleModel",
                "manufacturer": "SampleMfg",
                "location": "Sample Location",
                "latitude": 0.0,
                "longitude": 0.0,
                "original_timezone": "+00:00",
                "synced": 0,
                "enrichment_timestamp": datetime.now().isoformat(),
            }
        ],
        "aggregated": [
            {
                "window_start": datetime.now().isoformat(),
                "window_end": datetime.now().isoformat(),
                "sensor_id": "SCHEMA_SAMPLE",
                "avg_temperature": 22.0,
                "min_temperature": 20.0,
                "max_temperature": 24.0,
                "avg_humidity": 60.0,
                "avg_pressure": 101325.0,
                "avg_vibration": 0.5,
                "avg_voltage": 24.0,
                "record_count": 300,
                "anomaly_count": 0,
            }
        ],
        "anomalies": [
            {
                "id": 1,
                "timestamp": datetime.now().isoformat(),
                "sensor_id": "SCHEMA_SAMPLE",
                "temperature": 45.0,
                "humidity": 60.0,
                "pressure": 101325.0,
                "vibration": 2.5,
                "voltage": 24.0,
                "status_code": 1,
                "anomaly_flag": 1,
                "anomaly_type": "spike",
                "anomaly_score": 0.95,
                "firmware_version": "1.0.0",
                "model": "SampleModel",
                "manufacturer": "SampleMfg",
                "location": "Sample Location",
                "latitude": 0.0,
                "longitude": 0.0,
                "original_timezone": "+00:00",
                "synced": 0,
            }
        ],
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for stage, bucket in BUCKETS.items():
        try:
            sample_data = samples.get(stage, samples["ingestion"])
            json_content = json.dumps(sample_data, indent=2)

            # Write sample file to bucket
            file_path = f"{bucket}schema_sample_{timestamp}.json"
            dbutils.fs.put(file_path, json_content, overwrite=True)

            print(f"✅ {stage:12} : Uploaded schema sample")
        except Exception as e:
            print(f"❌ {stage:12} : Failed to upload sample: {str(e)[:50]}")

    print()
    print("📝 Schema samples uploaded for Auto Loader initialization")
    print()


def clear_all_buckets():
    """Clear all JSON files from S3 buckets and upload schema samples."""
    print("⚠️  CLEARING ALL JSON FILES FROM S3 BUCKETS")
    print("=" * 40)

    for stage, bucket in BUCKETS.items():
        try:
            files = dbutils.fs.ls(bucket)
            json_files = [f for f in files if f.name.endswith(".json")]

            if json_files:
                for file in json_files:
                    dbutils.fs.rm(file.path)
                print(f"✅ {stage:12} : Cleared {len(json_files)} JSON files")
            else:
                print(f"⚠️  {stage:12} : No JSON files to clear")

        except Exception as e:
            print(f"❌ {stage:12} : {str(e)[:50]}")
    print()

    # Upload schema samples after clearing
    upload_schema_samples()


# Always test access
test_bucket_access()

# Uncomment to clear all buckets and initialize with schema samples
# clear_all_buckets()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Functions

# COMMAND ----------


def create_pipeline(stage_name):
    """
    Create an Auto Loader pipeline for a specific stage.

    Args:
        stage_name: One of 'ingestion', 'validated', 'anomalies', 'enriched', 'aggregated'

    Returns:
        Streaming query object
    """
    bucket = BUCKETS[stage_name]
    table = TABLES[stage_name]

    # Read from S3 with Auto Loader
    df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", f"{SCHEMA_BASE}/{stage_name}")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.maxFilesPerTrigger", 100)
        .option("multiLine", "true")
        .load(bucket)
    )

    # Add processing timestamp
    df = df.withColumn("processing_timestamp", F.current_timestamp())

    # Write to Unity Catalog table
    query = (
        df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/{stage_name}/checkpoint")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)  # Process available data then stop
        .table(table)
    )

    return query


# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper Functions

# COMMAND ----------


def get_table_count(table_name):
    """Get current row count for a table."""
    try:
        return spark.sql(f"SELECT COUNT(*) FROM {table_name}").first()[0]
    except:
        return 0


def clear_checkpoints():
    """Clear all checkpoints to start fresh."""
    for stage in TABLES.keys():
        checkpoint_path = f"{CHECKPOINT_BASE}/{stage}/checkpoint/"
        try:
            dbutils.fs.rm(checkpoint_path, recurse=True)
            print(f"✅ Cleared {stage} checkpoint")
        except:
            print(f"⚠️  No checkpoint found for {stage}")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Clear Checkpoints (Run if needed to reprocess files)

# COMMAND ----------

# Uncomment to clear checkpoints and reprocess all files
# clear_checkpoints()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Polling Pipeline Runner
# MAGIC
# MAGIC This is the main loop that runs all pipelines on a schedule.

# COMMAND ----------


def run_pipeline_with_delay(stage_name, base_delay):
    """
    Run a single pipeline with a randomized delay.

    Args:
        stage_name: Pipeline stage to run
        base_delay: Base delay in seconds before starting

    Returns:
        Tuple of (stage_name, success, rows_processed, error_msg)
    """
    # Add random fuzzing: +/- 10% of base delay
    fuzz_factor = random.uniform(0.9, 1.1)
    actual_delay = base_delay * fuzz_factor

    # Sleep with fuzzing to avoid simultaneous starts
    time.sleep(actual_delay)

    try:
        query = create_pipeline(stage_name)

        # Wait for completion
        while query.isActive:
            time.sleep(0.5)

        # Check result
        if query.exception():
            return (stage_name, False, 0, str(query.exception())[:50])
        else:
            last_progress = query.lastProgress
            rows = last_progress.get("numInputRows", 0) if last_progress else 0
            return (stage_name, True, rows, None)

    except Exception as e:
        return (stage_name, False, 0, str(e)[:50])


def run_polling_pipelines():
    """
    Main polling loop that runs all 5 pipelines in parallel every POLL_INTERVAL_SECONDS.
    Includes fuzzing to avoid overloading.
    """
    print("🚀 STARTING AUTO LOADER POLLING (PARALLEL)")
    print("=" * 60)

    # Track initial counts
    initial_counts = {stage: get_table_count(TABLES[stage]) for stage in TABLES.keys()}
    print("\n📊 Initial row counts:")
    for stage, count in initial_counts.items():
        print(f"  {stage:12} : {count:,}")

    # Calculate end time
    end_time = datetime.now() + timedelta(minutes=RUNTIME_MINUTES)
    iteration = 0

    # Main polling loop
    while datetime.now() < end_time:
        iteration += 1
        remaining_minutes = int((end_time - datetime.now()).total_seconds() / 60)

        print(f"\n{'=' * 60}")
        print(
            f"🔄 Iteration #{iteration} - {datetime.now().strftime('%H:%M:%S')} ({remaining_minutes} min remaining)"
        )
        print("-" * 60)

        # Run all 5 pipelines in parallel with staggered starts
        print("  Starting pipelines in parallel with fuzzing...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all pipelines with small staggered delays
            futures = []
            for i, stage in enumerate(TABLES.keys()):
                # Stagger starts by 0-2 seconds with fuzzing
                base_delay = i * 0.5
                future = executor.submit(run_pipeline_with_delay, stage, base_delay)
                futures.append(future)
                print(f"    Submitted {stage:12} (delayed ~{base_delay:.1f}s ±10%)")

            # Wait for all to complete and collect results
            print("\n  Waiting for pipelines to complete...")
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Display results
        print("\n  Pipeline Results:")
        for stage_name, success, rows, error in sorted(results, key=lambda x: x[0]):
            if success:
                print(f"    {stage_name:12} : ✅ Processed {rows} rows")
            else:
                print(f"    {stage_name:12} : ❌ Failed: {error}")

        # Show current totals
        print("\n📊 Current row counts:")
        for stage in TABLES.keys():
            current_count = get_table_count(TABLES[stage])
            initial = initial_counts[stage]
            new_rows = current_count - initial
            print(f"  {stage:12} : {current_count:,} total (+{new_rows:,} new)")

        # Wait for next iteration with fuzzing
        if datetime.now() < end_time:
            # Fuzz the wait time too: +/- 10%
            fuzzed_wait = POLL_INTERVAL_SECONDS * random.uniform(0.9, 1.1)
            print(
                f"\n💤 Waiting {fuzzed_wait:.1f} seconds (base: {POLL_INTERVAL_SECONDS}s ±10%)..."
            )
            time.sleep(fuzzed_wait)

    # Final summary
    print(f"\n{'=' * 60}")
    print("✅ POLLING COMPLETE")
    print("\n📊 Final Summary:")
    for stage in TABLES.keys():
        final_count = get_table_count(TABLES[stage])
        initial = initial_counts[stage]
        total_new = final_count - initial
        print(f"  {stage:12} : {final_count:,} total (+{total_new:,} new rows)")


# Run the polling pipeline
run_polling_pipelines()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick Status Check
# MAGIC
# MAGIC Run this cell anytime to see current table counts.

# COMMAND ----------

print("📊 Current Table Status")
print("=" * 40)
for stage in TABLES.keys():
    count = get_table_count(TABLES[stage])
    print(f"{stage:12} : {count:,} rows")

# Check for active streams (should be none with availableNow trigger)
active = spark.streams.active
if active:
    print(f"\n⚠️  {len(active)} active streams found (unexpected)")
else:
    print("\n✅ No active streams (expected with availableNow trigger)")
