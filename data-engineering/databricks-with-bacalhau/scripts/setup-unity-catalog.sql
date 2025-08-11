-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Fix Unity Catalog External Locations
-- MAGIC 
-- MAGIC This notebook sets up external locations for S3 access in Unity Catalog.
-- MAGIC Run each section step by step.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Step 1: Check Current Setup

-- COMMAND ----------

-- Check if you have any storage credentials
SHOW STORAGE CREDENTIALS;

-- COMMAND ----------

-- Check existing external locations
SHOW EXTERNAL LOCATIONS;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Step 2: Create Storage Credential (Admin Only)
-- MAGIC 
-- MAGIC **Note**: This requires admin privileges. If you're not an admin, ask your admin to run this.

-- COMMAND ----------

-- MAGIC %python
-- MAGIC # Option A: If you have an IAM role for Databricks
-- MAGIC # Replace with your actual IAM role ARN
-- MAGIC spark.sql("""
-- MAGIC CREATE STORAGE CREDENTIAL IF NOT EXISTS expanso_s3_credential
-- MAGIC WITH (
-- MAGIC   TYPE = AWS_IAM_ROLE,
-- MAGIC   IAM_ROLE_ARN = 'arn:aws:iam::767397752906:role/databricks-s3-access'
-- MAGIC )
-- MAGIC """)

-- COMMAND ----------

-- MAGIC %python
-- MAGIC # Option B: If you need to use access keys (not recommended for production)
-- MAGIC # This is a temporary solution
-- MAGIC spark.conf.set("fs.s3a.access.key", dbutils.secrets.get(scope="aws", key="access_key"))
-- MAGIC spark.conf.set("fs.s3a.secret.key", dbutils.secrets.get(scope="aws", key="secret_key"))
-- MAGIC spark.conf.set("fs.s3a.endpoint", "s3.us-west-2.amazonaws.com")

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Step 3: Create External Locations for us-west-2

-- COMMAND ----------

-- Create external location for raw data bucket
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_raw_west2
URL 's3://expanso-databricks-raw-us-west-2/'
WITH (STORAGE CREDENTIAL expanso_s3_credential);

-- COMMAND ----------

-- Create external location for schematized data
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_schematized_west2
URL 's3://expanso-databricks-schematized-us-west-2/'
WITH (STORAGE CREDENTIAL expanso_s3_credential);

-- COMMAND ----------

-- Create external location for filtered data
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_filtered_west2
URL 's3://expanso-databricks-filtered-us-west-2/'
WITH (STORAGE CREDENTIAL expanso_s3_credential);

-- COMMAND ----------

-- Create external location for emergency data
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_emergency_west2
URL 's3://expanso-databricks-emergency-us-west-2/'
WITH (STORAGE CREDENTIAL expanso_s3_credential);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Step 4: Grant Permissions

-- COMMAND ----------

-- Grant permissions to use external locations
GRANT USE SCHEMA ON EXTERNAL LOCATION expanso_raw_west2 TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_raw_west2 TO `account users`;

GRANT USE SCHEMA ON EXTERNAL LOCATION expanso_schematized_west2 TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_schematized_west2 TO `account users`;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Step 5: Test Access

-- COMMAND ----------

-- Test listing files
LIST 's3://expanso-databricks-raw-us-west-2/raw/';

-- COMMAND ----------

-- Test reading JSON files
SELECT * FROM json.`s3://expanso-databricks-raw-us-west-2/raw/2025/08/03/*/sensor_data.json`
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Alternative: Create Tables Without External Paths
-- MAGIC 
-- MAGIC If you can't set up external locations, use managed tables instead:

-- COMMAND ----------

-- Create database without specifying location
CREATE DATABASE IF NOT EXISTS sensor_data;
USE sensor_data;

-- COMMAND ----------

-- Create managed table (Databricks manages the location)
CREATE TABLE IF NOT EXISTS sensor_readings_managed
USING DELTA
AS
SELECT 
  id,
  timestamp,
  sensor_id,
  temperature,
  humidity,
  pressure,
  battery_level,
  signal_strength,
  location,
  latitude,
  longitude,
  current_timestamp() as ingestion_time,
  date(timestamp) as date
FROM json.`s3://expanso-databricks-raw-us-west-2/raw/*/*/*/*/*.json`;

-- COMMAND ----------

-- Check the data
SELECT COUNT(*) as total_records FROM sensor_readings_managed;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Quick Fix: Direct Query Without External Locations
-- MAGIC 
-- MAGIC You can always query S3 directly if you have the right cluster permissions:

-- COMMAND ----------

-- MAGIC %python
-- MAGIC # Set S3 credentials at cluster level
-- MAGIC spark.conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
-- MAGIC spark.conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
-- MAGIC 
-- MAGIC # Read data directly
-- MAGIC df = spark.read.json("s3a://expanso-databricks-raw-us-west-2/raw/*/*/*/*/*.json")
-- MAGIC df.createOrReplaceTempView("sensor_data_temp")
-- MAGIC 
-- MAGIC # Query the data
-- MAGIC spark.sql("SELECT COUNT(*) FROM sensor_data_temp").show()

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Summary
-- MAGIC 
-- MAGIC 1. **Best Option**: Set up storage credential and external locations (requires admin)
-- MAGIC 2. **Alternative**: Use managed tables without specifying locations
-- MAGIC 3. **Quick Fix**: Configure S3 access at cluster level
-- MAGIC 
-- MAGIC The error occurs because Unity Catalog enforces governance - it needs to know which S3 locations you're allowed to access.