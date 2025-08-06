# Databricks notebook source
# MAGIC %md
# MAGIC # Complete Teardown - Delete ALL Data
# MAGIC 
# MAGIC This notebook deletes ALL data from sensor_data tables.
# MAGIC 
# MAGIC **WARNING**: This will delete ALL data, not just demo data!

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

from datetime import datetime, timezone

# Configuration
CATALOG = "expanso_databricks_workspace"
DATABASE = "sensor_data"
CHECKPOINT_BASE = "s3://expanso-databricks-checkpoints-us-west-2/demo-checkpoints"
METADATA_BUCKET = "s3://expanso-databricks-metadata-us-west-2"

print("🧹 COMPLETE TEARDOWN - This will delete ALL data!")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Stop ALL Streams

# COMMAND ----------

print("🛑 Stopping ALL active streams...")

active_streams = spark.streams.active
if active_streams:
    print("Found " + str(len(active_streams)) + " active streams")
    for stream in active_streams:
        print("  Stopping: " + stream.id)
        stream.stop()
    print("✓ All streams stopped")
else:
    print("✓ No active streams")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Delete ALL Data

# COMMAND ----------

# Tables to clean
TABLES = [
    CATALOG + "." + DATABASE + ".sensor_data_ingestion",
    CATALOG + "." + DATABASE + ".sensor_data_validated", 
    CATALOG + "." + DATABASE + ".sensor_data_enriched",
    CATALOG + "." + DATABASE + ".sensor_data_aggregated"
]

total_deleted = 0

for table in TABLES:
    try:
        # Count records
        count = spark.sql("SELECT COUNT(*) as cnt FROM " + table).collect()[0]['cnt']
        
        if count > 0:
            # Delete ALL data
            spark.sql("DELETE FROM " + table)
            spark.sql("OPTIMIZE " + table)
            print("✓ Deleted " + str(count) + " records from " + table)
            total_deleted += count
        else:
            print("  - " + table + " is already empty")
            
    except Exception as e:
        print("  ⚠️  " + table + ": " + str(e))

print("\nTotal records deleted: " + str(total_deleted))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Clean ALL Checkpoints and Metadata

# COMMAND ----------

print("\n🗑️  Cleaning all checkpoints and metadata...")

# Remove all checkpoints
try:
    dbutils.fs.rm(CHECKPOINT_BASE, recurse=True)
    print("✓ Removed all checkpoints")
except:
    print("  - No checkpoints to remove")

# Remove all metadata
try:
    dbutils.fs.rm(METADATA_BUCKET + "/demo-metadata/", recurse=True)
    print("✓ Removed all metadata")
except:
    print("  - No metadata to remove")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("\n" + "="*60)
print("✅ COMPLETE TEARDOWN FINISHED!")
print("="*60)
print("\n  - All streams stopped")
print("  - All data deleted (" + str(total_deleted) + " records)")
print("  - All checkpoints removed")
print("  - All metadata removed")
print("\n✅ Tables still exist but are completely empty")
print("✅ Ready for fresh start")