# Databricks notebook source
# MAGIC %md
# MAGIC # Test Auto Loader Access
# MAGIC This notebook tests access to S3 buckets through Unity Catalog

# COMMAND ----------

# Test basic access
print("Testing S3 access through Unity Catalog...")

buckets = {
    "ingestion": "s3://expanso-databricks-ingestion-us-west-2/",
    "checkpoints": "s3://expanso-databricks-checkpoints-us-west-2/"
}

for name, path in buckets.items():
    try:
        files = dbutils.fs.ls(path)
        print(f"✅ {name}: {path} - Success ({len(files)} items)")
    except Exception as e:
        print(f"❌ {name}: {path} - Failed: {e}")

# COMMAND ----------

# Test Auto Loader with minimal configuration
print("\nTesting Auto Loader...")

test_path = "s3://expanso-databricks-ingestion-us-west-2/test/"
checkpoint_path = "s3://expanso-databricks-checkpoints-us-west-2/test-autoloader/"

# Create test data
test_data = spark.range(1).selectExpr("id", "current_timestamp() as ts")
test_data.write.mode("overwrite").json(test_path)
print(f"✅ Created test data at {test_path}")

# Try to read with Auto Loader
try:
    df = (spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", checkpoint_path + "schema")
        .load(test_path))
    
    # Start a simple query
    query = (df.writeStream
        .format("memory")
        .queryName("test_stream")
        .option("checkpointLocation", checkpoint_path + "checkpoint")
        .start())
    
    print("✅ Auto Loader stream started successfully")
    query.stop()
    
except Exception as e:
    print(f"❌ Auto Loader failed: {e}")
    import traceback
    traceback.print_exc()

# COMMAND ----------

# Check which storage credential is being used
print("\nChecking storage credentials...")
spark.sql("SHOW STORAGE CREDENTIALS").show(truncate=False)

# COMMAND ----------

# Check external locations
print("\nChecking external locations...")
spark.sql("SHOW EXTERNAL LOCATIONS").show(truncate=False)