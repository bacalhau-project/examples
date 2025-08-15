# Databricks notebook source
# MAGIC %md
# MAGIC # Simple Auto Loader Polling Pipeline
# MAGIC
# MAGIC This notebook runs 4 independent Auto Loader pipelines that continuously ingest data from S3 buckets to Unity Catalog tables.
# MAGIC
# MAGIC **Architecture:**
# MAGIC - 4 S3 buckets (ingestion, validated, enriched, aggregated) receive data from external service
# MAGIC - 4 Auto Loader pipelines read from these buckets
# MAGIC - Data is written to 4 corresponding Unity Catalog tables
# MAGIC - Pipelines restart every 30 seconds to process new files

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

from pyspark.sql import functions as F
import time
from datetime import datetime, timedelta

# Catalog and Schema
CATALOG = "expanso_databricks_workspace"
SCHEMA = "sensor_readings"

# S3 Buckets (source)
BUCKETS = {
    "ingestion": "s3://expanso-databricks-ingestion-us-west-2/",
    "validated": "s3://expanso-databricks-validated-us-west-2/",
    "enriched": "s3://expanso-databricks-enriched-us-west-2/",
    "aggregated": "s3://expanso-databricks-aggregated-us-west-2/",
}

# Unity Catalog Tables (destination)
TABLES = {
    "ingestion": f"{CATALOG}.{SCHEMA}.sensor_readings_ingestion",
    "validated": f"{CATALOG}.{SCHEMA}.sensor_readings_validated",
    "enriched": f"{CATALOG}.{SCHEMA}.sensor_readings_enriched",
    "aggregated": f"{CATALOG}.{SCHEMA}.sensor_readings_aggregated",
}

# Checkpoint and Schema Locations
CHECKPOINT_BASE = "s3://expanso-databricks-checkpoints-us-west-2"
SCHEMA_BASE = "s3://expanso-databricks-metadata-us-west-2/schemas"

# Polling Configuration
POLL_INTERVAL_SECONDS = 30  # How often to restart pipelines
RUNTIME_MINUTES = 60  # Total runtime

print("✅ Configuration loaded")
print(f"📊 Tables: {', '.join(TABLES.keys())}")
print(f"⏱️  Poll every {POLL_INTERVAL_SECONDS} seconds for {RUNTIME_MINUTES} minutes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Functions

# COMMAND ----------


def create_pipeline(stage_name):
    """
    Create an Auto Loader pipeline for a specific stage.

    Args:
        stage_name: One of 'ingestion', 'validated', 'enriched', 'aggregated'

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


def run_polling_pipelines():
    """
    Main polling loop that runs all 4 pipelines every POLL_INTERVAL_SECONDS.
    """
    print("🚀 STARTING AUTO LOADER POLLING")
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

        # Start all 4 pipelines
        for stage in TABLES.keys():
            try:
                print(f"  Starting {stage:12} pipeline...", end="")
                query = create_pipeline(stage)

                # Wait for completion (availableNow trigger processes then stops)
                while query.isActive:
                    time.sleep(0.5)

                # Check result
                if query.exception():
                    print(f" ❌ Failed: {str(query.exception())[:50]}")
                else:
                    last_progress = query.lastProgress
                    rows_processed = (
                        last_progress.get("numInputRows", 0) if last_progress else 0
                    )
                    print(f" ✅ Processed {rows_processed} rows")

            except Exception as e:
                print(f" ❌ Error: {str(e)[:50]}")

        # Show current totals
        print("\n📊 Current row counts:")
        for stage in TABLES.keys():
            current_count = get_table_count(TABLES[stage])
            initial = initial_counts[stage]
            new_rows = current_count - initial
            print(f"  {stage:12} : {current_count:,} total (+{new_rows:,} new)")

        # Wait for next iteration
        if datetime.now() < end_time:
            print(f"\n💤 Waiting {POLL_INTERVAL_SECONDS} seconds...")
            time.sleep(POLL_INTERVAL_SECONDS)

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
