 # Databricks ↔ AWS S3 Connectivity Guide
 
 This guide provides sample notebook cells to configure and verify secure connectivity between Databricks and AWS S3.
 
 ## Prerequisites
 - AWS credentials should be stored securely in a Databricks Secret Scope (e.g., `my-secrets`).
 - The S3 bucket name should be provided via a notebook widget or environment variable (`S3_BUCKET_NAME`).
 
 ## 1. Configure AWS Credentials in Spark
 In a Python cell, configure Spark to use AWS credentials from the secret scope:
 ```python
 # Replace 'my-secrets' with your secret scope name
 access_key = dbutils.secrets.get("my-secrets", "AWS_ACCESS_KEY_ID")
 secret_key = dbutils.secrets.get("my-secrets", "AWS_SECRET_ACCESS_KEY")

 spark.conf.set("fs.s3a.access.key", access_key)
 spark.conf.set("fs.s3a.secret.key", secret_key)
 spark.conf.set("fs.s3a.endpoint", "s3.amazonaws.com")
 ```
 
 ## 2. List Bucket Contents
 Use `dbutils.fs.ls` to confirm connectivity:
 ```python
 bucket = dbutils.widgets.get("S3_BUCKET_NAME")  # or set manually
 display(dbutils.fs.ls(f"s3a://{bucket}/"))
 ```
 
 ## 3. Read a Sample Parquet File
 Read and display a sample Parquet file for a known sensor ID:
 ```python
 sensor_id = "<SENSOR_ID>"
 df = spark.read.parquet(f"s3a://{bucket}/{sensor_id}.parquet")
 display(df.limit(10))
 ```
 
 If all cells execute without errors, your Databricks workspace is correctly configured to read from AWS S3.