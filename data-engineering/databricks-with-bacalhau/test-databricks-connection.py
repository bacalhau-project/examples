#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sql-connector",
#   "python-dotenv",
# ]
# ///

"""Test Databricks connection."""

import os
from pathlib import Path
from databricks import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

host = os.getenv("DATABRICKS_HOST", "").rstrip("/").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN", "")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "")

print(f"Host: {host}")
print(f"Token: {'*' * 10 if token else 'NOT SET'}")
print(f"HTTP Path: {http_path}")

if not all([host, token, http_path]):
    print("ERROR: Missing required environment variables")
    exit(1)

print("\nConnecting to Databricks...")
try:
    conn = sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT current_catalog(), current_database()")
    result = cursor.fetchone()
    
    print(f"✓ Connected successfully!")
    print(f"  Current catalog: {result[0]}")
    print(f"  Current database: {result[1]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Connection failed: {e}")