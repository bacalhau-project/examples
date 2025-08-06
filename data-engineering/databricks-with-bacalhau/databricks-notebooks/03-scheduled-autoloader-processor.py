# Databricks notebook source
# MAGIC %md
# MAGIC # Scheduled Auto Loader Processor
# MAGIC 
# MAGIC This lightweight notebook is designed to be scheduled every 5-10 minutes to process new files.
# MAGIC It includes safety checks to ensure it doesn't run past the 24-hour demo window.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check Demo Status

# COMMAND ----------

from datetime import datetime, timezone
import json

# Parameters
dbutils.widgets.text("demo_id", "", "Demo ID")
demo_id = dbutils.widgets.get("demo_id")

if not demo_id:
    dbutils.notebook.exit("No demo_id provided")

# Configuration
CATALOG = "expanso_databricks_workspace"
DATABASE = "sensor_data"
METADATA_BUCKET = "s3://expanso-databricks-metadata-us-west-2"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Demo is Active

# COMMAND ----------

# Check if demo is still active
try:
    setup_path = f"{METADATA_BUCKET}/demo-metadata/{demo_id}/setup_summary.json"
    setup_data = json.loads(dbutils.fs.head(setup_path))
    
    auto_shutdown_time = datetime.fromisoformat(
        setup_data['demo_metadata']['auto_shutdown_time'].replace('Z', '+00:00')
    )
    
    if datetime.now(timezone.utc) > auto_shutdown_time:
        print(f"⏰ Demo {demo_id} has expired. Stopping processing.")
        dbutils.notebook.exit("Demo expired")
        
    print(f"✓ Demo {demo_id} is active")
    print(f"  Time remaining: {(auto_shutdown_time - datetime.now(timezone.utc)).total_seconds() / 3600:.1f} hours")
    
except Exception as e:
    print(f"❌ Could not verify demo status: {str(e)}")
    dbutils.notebook.exit("Could not verify demo")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process New Files

# COMMAND ----------

# Process new files for each stage
from pyspark.sql.types import *
from pyspark.sql.functions import *

BUCKETS = {
    "ingestion": "s3://expanso-databricks-ingestion-us-west-2/ingestion/",
    "validated": "s3://expanso-databricks-validated-us-west-2/validated/",
    "enriched": "s3://expanso-databricks-enriched-us-west-2/enriched/",
    "aggregated": "s3://expanso-databricks-aggregated-us-west-2/aggregated/"
}

TABLES = {
    "ingestion": f"{CATALOG}.{DATABASE}.sensor_data_ingestion",
    "validated": f"{CATALOG}.{DATABASE}.sensor_data_validated",
    "enriched": f"{CATALOG}.{DATABASE}.sensor_data_enriched",
    "aggregated": f"{CATALOG}.{DATABASE}.sensor_data_aggregated"
}

CHECKPOINT_BASE = f"s3://expanso-databricks-checkpoints-us-west-2/demo-checkpoints/{demo_id}"

# Simple schema for ingestion
ingestion_schema = StructType([
    StructField("metadata", MapType(StringType(), StringType()), True),
    StructField("records", ArrayType(MapType(StringType(), StringType())), True),
    StructField("_autoloader_metadata", MapType(StringType(), StringType()), True)
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process Ingestion Stage

# COMMAND ----------

# Process ingestion stage
stage = "ingestion"
print(f"\n📥 Processing {stage} stage...")

try:
    df = (spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("multiLine", "true")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINT_BASE}/{stage}/schema")
        .option("cloudFiles.maxFilesPerTrigger", 10)
        .load(BUCKETS[stage]))
    
    processed_df = (df
        .select(explode(col("records")).alias("record"))
        .select("record.*")
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_pipeline_stage", lit(stage))
        .withColumn("_demo_id", lit(demo_id)))
    
    query = (processed_df.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/{stage}")
        .trigger(availableNow=True)
        .table(TABLES[stage]))
    
    query.awaitTermination()
    
    # Count new records
    new_records = spark.sql(f"""
        SELECT COUNT(*) as count 
        FROM {TABLES[stage]} 
        WHERE _demo_id = '{demo_id}' 
        AND _ingested_at >= current_timestamp() - INTERVAL 10 MINUTES
    """).collect()[0]['count']
    
    print(f"✓ Processed {new_records} new records in {stage}")
    
except Exception as e:
    print(f"⚠️  Error processing {stage}: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Update Monitoring Dashboard

# COMMAND ----------

# Update monitoring dashboard
try:
    dashboard_data = {
        "demo_id": demo_id,
        "last_run": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "stages_processed": ["ingestion"],
        "new_records": {
            "ingestion": new_records if 'new_records' in locals() else 0
        }
    }
    
    dbutils.fs.put(
        f"{METADATA_BUCKET}/demo-metadata/{demo_id}/last_run.json",
        json.dumps(dashboard_data, indent=2),
        overwrite=True
    )
    
    print(f"\n✓ Scheduled processing complete for demo {demo_id}")
    
except Exception as e:
    print(f"⚠️  Could not update dashboard: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return Summary

# COMMAND ----------

# Return summary
dbutils.notebook.exit(json.dumps({
    "demo_id": demo_id,
    "status": "success",
    "records_processed": new_records if 'new_records' in locals() else 0,
    "timestamp": datetime.now(timezone.utc).isoformat()
}))