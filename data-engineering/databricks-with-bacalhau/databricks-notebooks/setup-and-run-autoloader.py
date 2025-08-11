# Databricks notebook source
# MAGIC %md
# MAGIC # Flexible Sensor Data Ingestion Pipeline
# MAGIC 
# MAGIC This notebook sets up Auto Loader pipelines that can handle multiple JSON formats:
# MAGIC - Old wrapped format: `{"records": [...]}`
# MAGIC - Old flat format: `[{"battery_level": ..., "signal_strength": ...}]`
# MAGIC - New sensor format: `[{"temperature": ..., "humidity": ..., "pressure": ...}]`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from datetime import datetime, timedelta
import time
import json

# Configuration
CATALOG = "expanso_databricks_workspace"
SCHEMA = "sensor_readings"
RUNTIME_MINUTES = 60  # How long to run the pipelines

# S3 Buckets
INGESTION_BUCKET = "s3://expanso-databricks-ingestion-us-west-2/ingestion/"
VALIDATED_BUCKET = "s3://expanso-databricks-validated-us-west-2/validated/"
ENRICHED_BUCKET = "s3://expanso-databricks-enriched-us-west-2/enriched/"
AGGREGATED_BUCKET = "s3://expanso-databricks-aggregated-us-west-2/aggregated/"
CHECKPOINT_BUCKET = "s3://expanso-databricks-checkpoints-us-west-2/"

# Table names
INGESTION_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_ingestion"
VALIDATED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_validated"
ENRICHED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_enriched"
AGGREGATED_TABLE = f"{CATALOG}.{SCHEMA}.sensor_readings_aggregated"
PIPELINE_STATUS_TABLE = f"{CATALOG}.{SCHEMA}.pipeline_status"

print(f"✅ Configuration loaded")
print(f"📊 Target catalog: {CATALOG}.{SCHEMA}")
print(f"⏱️  Runtime: {RUNTIME_MINUTES} minutes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Database and Tables

# COMMAND ----------

# Create catalog and schema if they don't exist
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"✅ Using catalog: {CATALOG}")
print(f"✅ Using schema: {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Flexible Ingestion Pipeline (Handles All Formats)

# COMMAND ----------

def create_flexible_ingestion_pipeline():
    """Create ingestion pipeline that handles multiple JSON formats"""
    
    print("🚀 Starting flexible ingestion pipeline...")
    
    # Read stream with flexible schema handling
    df = spark.readStream \
        .format("cloudFiles") \
        .option("cloudFiles.format", "json") \
        .option("cloudFiles.schemaLocation", CHECKPOINT_BUCKET + "ingestion_flexible/schema") \
        .option("cloudFiles.inferColumnTypes", "true") \
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns") \
        .option("cloudFiles.maxFilesPerTrigger", 100) \
        .option("multiLine", "true") \
        .option("rescuedDataColumn", "_rescued_data") \
        .load(INGESTION_BUCKET)
    
    # Process the data to handle both formats
    processed_df = df \
        .withColumn("raw_json", to_json(struct("*"))) \
        .withColumn("has_records_field", col("records").isNotNull()) \
        .withColumn("has_battery_field", col("battery_level").isNotNull()) \
        .withColumn("has_temperature_field", col("temperature").isNotNull()) \
        .withColumn(
            "data_format",
            when(col("has_records_field"), "wrapped_old")
            .when(col("has_battery_field"), "flat_old")
            .when(col("has_temperature_field"), "new_sensor")
            .otherwise("unknown")
        )
    
    # Handle wrapped format by exploding the records array
    unwrapped_df = processed_df \
        .withColumn(
            "record",
            when(col("data_format") == "wrapped_old", explode_outer(col("records")))
            .otherwise(struct("*"))
        )
    
    # Normalize all formats into a common schema
    final_df = unwrapped_df \
        .select(
            # Common timestamp field
            coalesce(
                col("record.timestamp"),
                col("timestamp"),
                col("record.created_at"),
                col("created_at"),
                current_timestamp()
            ).cast("timestamp").alias("timestamp"),
            
            # Sensor identification
            coalesce(
                col("record.sensor_id"),
                col("sensor_id"),
                lit("UNKNOWN")
            ).alias("sensor_id"),
            
            # Old format fields (battery/signal)
            coalesce(
                col("record.battery_level"),
                col("battery_level")
            ).cast("double").alias("battery_level"),
            
            coalesce(
                col("record.signal_strength"),
                col("signal_strength")
            ).cast("double").alias("signal_strength"),
            
            # New format fields (environmental)
            coalesce(
                col("record.temperature"),
                col("temperature")
            ).cast("double").alias("temperature"),
            
            coalesce(
                col("record.humidity"),
                col("humidity")
            ).cast("double").alias("humidity"),
            
            coalesce(
                col("record.pressure"),
                col("pressure")
            ).cast("double").alias("pressure"),
            
            coalesce(
                col("record.vibration"),
                col("vibration")
            ).cast("double").alias("vibration"),
            
            coalesce(
                col("record.voltage"),
                col("voltage")
            ).cast("double").alias("voltage"),
            
            coalesce(
                col("record.status_code"),
                col("status_code")
            ).cast("int").alias("status_code"),
            
            coalesce(
                col("record.anomaly_flag"),
                col("anomaly_flag")
            ).cast("int").alias("anomaly_flag"),
            
            # Location data
            coalesce(
                col("record.location"),
                col("location")
            ).alias("location"),
            
            coalesce(
                col("record.latitude"),
                col("latitude")
            ).cast("double").alias("latitude"),
            
            coalesce(
                col("record.longitude"),
                col("longitude")
            ).cast("double").alias("longitude"),
            
            # Metadata
            col("data_format").alias("source_format"),
            current_timestamp().alias("ingestion_timestamp"),
            input_file_name().alias("source_file"),
            col("_rescued_data").alias("rescued_data")
        ) \
        .filter(
            (col("timestamp").isNotNull()) & 
            (
                col("battery_level").isNotNull() | 
                col("temperature").isNotNull()
            )
        )  # Must have timestamp and at least one data field
    
    # Write to Delta table
    query = final_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", CHECKPOINT_BUCKET + "ingestion_flexible/output") \
        .option("mergeSchema", "true") \
        .trigger(availableNow=True) \
        .table(INGESTION_TABLE)
    
    return query

# Start the ingestion pipeline
ingestion_query = create_flexible_ingestion_pipeline()
print("✅ Flexible ingestion pipeline started")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Validation Pipeline

# COMMAND ----------

def create_validation_pipeline():
    """Create validation pipeline"""
    
    # Read from ingestion table
    df = spark.readStream \
        .format("delta") \
        .table(INGESTION_TABLE)
    
    # Apply validation rules based on data format
    validated_df = df \
        .withColumn(
            "is_valid",
            when(
                col("source_format").isin("flat_old", "wrapped_old"),
                (col("battery_level").between(0, 200)) & 
                (col("signal_strength").between(0, 100))
            ).when(
                col("source_format") == "new_sensor",
                (col("temperature").between(-50, 150)) & 
                (col("humidity").between(0, 100)) &
                (col("pressure").between(0, 2000)) &
                (col("voltage").between(0, 50))
            ).otherwise(False)
        ) \
        .filter(col("is_valid") == True) \
        .drop("is_valid")
    
    # Write validated data
    query = validated_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", CHECKPOINT_BUCKET + "validated/") \
        .trigger(availableNow=True) \
        .table(VALIDATED_TABLE)
    
    return query

# Start validation pipeline
validation_query = create_validation_pipeline()
print("✅ Validation pipeline started")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Enrichment Pipeline

# COMMAND ----------

def create_enrichment_pipeline():
    """Create enrichment pipeline"""
    
    # Read from validated table
    df = spark.readStream \
        .format("delta") \
        .table(VALIDATED_TABLE)
    
    # Add enrichment based on data type
    enriched_df = df \
        .withColumn("processing_timestamp", current_timestamp()) \
        .withColumn("day_of_week", dayofweek("timestamp")) \
        .withColumn("hour_of_day", hour("timestamp")) \
        .withColumn(
            "data_quality_score",
            when(
                col("source_format").isin("flat_old", "wrapped_old"),
                when(col("battery_level").isNotNull() & col("signal_strength").isNotNull(), 1.0)
                .otherwise(0.5)
            ).when(
                col("source_format") == "new_sensor",
                (
                    when(col("temperature").isNotNull(), 0.25).otherwise(0) +
                    when(col("humidity").isNotNull(), 0.25).otherwise(0) +
                    when(col("pressure").isNotNull(), 0.25).otherwise(0) +
                    when(col("voltage").isNotNull(), 0.25).otherwise(0)
                )
            ).otherwise(0.0)
        ) \
        .withColumn(
            "alert_level",
            when(
                col("source_format").isin("flat_old", "wrapped_old"),
                when(col("battery_level") < 20, "critical")
                .when(col("battery_level") < 50, "warning")
                .otherwise("normal")
            ).when(
                col("source_format") == "new_sensor",
                when(col("anomaly_flag") == 1, "critical")
                .when(col("temperature") > 100, "warning")
                .when(col("pressure") > 1500, "warning")
                .otherwise("normal")
            ).otherwise("unknown")
        )
    
    # Write enriched data
    query = enriched_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", CHECKPOINT_BUCKET + "enriched/") \
        .trigger(availableNow=True) \
        .table(ENRICHED_TABLE)
    
    return query

# Start enrichment pipeline
enrichment_query = create_enrichment_pipeline()
print("✅ Enrichment pipeline started")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Aggregation Pipeline

# COMMAND ----------

def create_aggregation_pipeline():
    """Create aggregation pipeline with watermarking"""
    
    # Read from enriched table
    df = spark.readStream \
        .format("delta") \
        .table(ENRICHED_TABLE)
    
    # Aggregate by time window and sensor
    aggregated_df = df \
        .withWatermark("timestamp", "1 hour") \
        .groupBy(
            window("timestamp", "5 minutes"),
            "sensor_id",
            "source_format"
        ) \
        .agg(
            count("*").alias("record_count"),
            
            # Old format aggregations
            avg("battery_level").alias("avg_battery_level"),
            min("battery_level").alias("min_battery_level"),
            max("battery_level").alias("max_battery_level"),
            avg("signal_strength").alias("avg_signal_strength"),
            
            # New format aggregations
            avg("temperature").alias("avg_temperature"),
            avg("humidity").alias("avg_humidity"),
            avg("pressure").alias("avg_pressure"),
            avg("voltage").alias("avg_voltage"),
            sum(when(col("anomaly_flag") == 1, 1).otherwise(0)).alias("anomaly_count"),
            
            # Alert counts
            sum(when(col("alert_level") == "critical", 1).otherwise(0)).alias("critical_alerts"),
            sum(when(col("alert_level") == "warning", 1).otherwise(0)).alias("warning_alerts")
        ) \
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "*"
        ) \
        .drop("window")
    
    # Write aggregated data
    query = aggregated_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", CHECKPOINT_BUCKET + "aggregated/") \
        .trigger(availableNow=True) \
        .table(AGGREGATED_TABLE)
    
    return query

# Start aggregation pipeline
aggregation_query = create_aggregation_pipeline()
print("✅ Aggregation pipeline started")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Monitor Pipeline Progress

# COMMAND ----------

def monitor_pipelines(runtime_minutes=60):
    """Monitor all pipelines for specified duration"""
    
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=runtime_minutes)
    
    print(f"🕐 Start time: {start_time}")
    print(f"🛑 Scheduled shutdown: {end_time}")
    print("=" * 60)
    
    batch_num = 0
    while datetime.now() < end_time:
        batch_num += 1
        print(f"\n📦 Batch #{batch_num} - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)
        
        # Check each pipeline
        pipelines = {
            "ingestion": ingestion_query,
            "validated": validation_query,
            "enriched": enrichment_query,
            "aggregated": aggregation_query
        }
        
        for name, query in pipelines.items():
            try:
                status = query.status
                if status['isDataAvailable']:
                    last_progress = query.lastProgress
                    if last_progress and 'numInputRows' in last_progress:
                        rows = last_progress['numInputRows']
                        if rows > 0:
                            print(f"   Processing {name}... ✅ {rows} records")
                        else:
                            print(f"   Processing {name}... ⏸️  No new files")
                    else:
                        print(f"   Processing {name}... ⏸️  No new files")
                else:
                    print(f"   Processing {name}... ⏸️  Waiting for data")
            except Exception as e:
                print(f"   ⚠️  Error in {name}: {str(e)}")
        
        # Show summary
        try:
            ingestion_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {INGESTION_TABLE}").collect()[0]['cnt']
            validated_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {VALIDATED_TABLE}").collect()[0]['cnt']
            enriched_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {ENRICHED_TABLE}").collect()[0]['cnt']
            aggregated_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {AGGREGATED_TABLE}").collect()[0]['cnt']
            
            print(f"\n   📊 Total records:")
            print(f"      Ingestion: {ingestion_count:,}")
            print(f"      Validated: {validated_count:,}")
            print(f"      Enriched: {enriched_count:,}")
            print(f"      Aggregated: {aggregated_count:,}")
        except:
            pass
        
        remaining = int((end_time - datetime.now()).total_seconds() / 60)
        print(f"\n   ⏱️  Time remaining: {remaining} minutes")
        print(f"   💤 Waiting 10 seconds...")
        
        time.sleep(10)
    
    print("\n" + "=" * 60)
    print("⏹️  Stopping all pipelines...")
    
    # Stop all pipelines
    for name, query in pipelines.items():
        try:
            query.stop()
            print(f"   ✅ {name} pipeline stopped")
        except:
            pass
    
    print("\n✅ All pipelines completed successfully!")
    
    # Final summary
    print("\n📊 FINAL SUMMARY:")
    print("-" * 40)
    for table in [INGESTION_TABLE, VALIDATED_TABLE, ENRICHED_TABLE, AGGREGATED_TABLE]:
        try:
            count = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()[0]['cnt']
            print(f"   {table.split('.')[-1]}: {count:,} records")
        except:
            print(f"   {table.split('.')[-1]}: No data")

# Start monitoring
monitor_pipelines(RUNTIME_MINUTES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Query Results

# COMMAND ----------

# Show sample of ingested data with different formats
display(spark.sql(f"""
    SELECT 
        timestamp,
        sensor_id,
        source_format,
        battery_level,
        signal_strength,
        temperature,
        humidity,
        pressure,
        voltage,
        anomaly_flag
    FROM {INGESTION_TABLE}
    ORDER BY timestamp DESC
    LIMIT 20
"""))

# COMMAND ----------

# Show data format distribution
display(spark.sql(f"""
    SELECT 
        source_format,
        COUNT(*) as record_count,
        MIN(timestamp) as earliest_record,
        MAX(timestamp) as latest_record
    FROM {INGESTION_TABLE}
    GROUP BY source_format
    ORDER BY record_count DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Complete!
# MAGIC 
# MAGIC The flexible ingestion pipeline is now running and can handle:
# MAGIC - Old wrapped format with battery/signal data
# MAGIC - Old flat format with battery/signal data  
# MAGIC - New sensor format with environmental data
# MAGIC - Future schema changes through schema evolution
# MAGIC 
# MAGIC All formats are normalized into a unified schema with appropriate null values where data doesn't exist.