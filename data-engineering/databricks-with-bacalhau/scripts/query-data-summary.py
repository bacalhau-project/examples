#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "tabulate>=0.9.0",
#     "boto3>=1.28.0",
#     "colorama>=0.4.6",
# ]
# ///

"""Query summary of all data in S3 buckets and Unity Catalog tables."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from databricks import sql
from tabulate import tabulate
import boto3
from datetime import datetime, timedelta, timezone
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Load environment variables
load_dotenv()


def print_header(title, color=Fore.CYAN):
    """Print a formatted header."""
    print(f"\n{color}{'=' * 70}{Style.RESET_ALL}")
    print(f"{color}{title}{Style.RESET_ALL}")
    print(f"{color}{'=' * 70}{Style.RESET_ALL}")


def print_timestamp_info():
    """Print information about timestamps used in the system."""
    print(f"\n{Fore.CYAN}📅 TIMESTAMP INFORMATION:{Style.RESET_ALL}")
    print(
        f"  • S3 Status: Based on {Fore.YELLOW}LastModified{Style.RESET_ALL} (when file was uploaded to S3)"
    )
    print(
        f"  • Databricks Status: Based on {Fore.YELLOW}timestamp{Style.RESET_ALL} column (sensor reading time)"
    )
    print(f"  • All times compared against {Fore.YELLOW}current UTC{Style.RESET_ALL} time")
    print(f"  • Note: Sensor timestamps may differ from upload times by seconds/minutes")
    print("")


def format_timestamp(ts):
    """Format timestamp for display."""
    if not ts:
        return "N/A"
    if isinstance(ts, str):
        return ts[:19]
    try:
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)[:19]


def check_data_freshness(latest_time):
    """Check how fresh the data is and return status.

    Note: This compares against current UTC time since all our timestamps
    are in UTC (S3 LastModified, Databricks timestamps).
    """
    if not latest_time:
        return "❌", "No data"

    try:
        # Parse timestamp to UTC datetime
        if isinstance(latest_time, str):
            # Parse string timestamp
            if "T" in latest_time:
                # ISO format timestamp (may have timezone)
                if "+" in latest_time or latest_time.endswith("Z"):
                    # Has timezone info
                    dt_str = latest_time.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str.split("+")[0])
                else:
                    dt = datetime.fromisoformat(latest_time.split(".")[0])
            else:
                # Simple datetime format
                dt = datetime.strptime(latest_time[:19], "%Y-%m-%d %H:%M:%S")
        elif hasattr(latest_time, "replace"):
            # It's a datetime object, may be timezone aware
            dt = latest_time.replace(tzinfo=None)
        else:
            dt = latest_time

        # Use UTC now for comparison since our data is in UTC
        from datetime import timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = now - dt

        # Calculate total hours for accurate display
        total_hours = diff.total_seconds() / 3600

        if diff < timedelta(minutes=5):
            return "🟢", "LIVE (< 5 min)"
        elif diff < timedelta(hours=1):
            mins = int(diff.total_seconds() / 60)
            return "🟡", f"RECENT ({mins} min ago)"
        elif diff < timedelta(hours=24):
            if total_hours < 2:
                return "🟠", f"STALE ({int(total_hours * 60)} min ago)"
            else:
                return "🟠", f"STALE ({int(total_hours)} hours ago)"
        else:
            days = diff.days
            if days == 1:
                return "🔴", f"OLD (1 day ago)"
            else:
                return "🔴", f"OLD ({days} days ago)"
    except Exception as e:
        return "⚪", f"Unknown (parse error)"


def query_unity_catalog():
    """Query all tables in Unity Catalog and show summary."""

    print_header("📊 DATABRICKS UNITY CATALOG SUMMARY")

    # Get Databricks credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")

    # Extract warehouse ID from HTTP_PATH
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
    if "/warehouses/" in http_path:
        warehouse_id = http_path.split("/warehouses/")[-1]
    else:
        print(f"{Fore.RED}❌ Invalid or missing DATABRICKS_HTTP_PATH{Style.RESET_ALL}")
        sys.exit(1)

    # Get database/schema
    database = os.getenv("DATABRICKS_DATABASE", "sensor_readings")
    if not database:
        print(f"{Fore.RED}❌ Missing DATABRICKS_DATABASE{Style.RESET_ALL}")
        sys.exit(1)

    # Catalog is fixed, schema is from environment
    catalog = "expanso_databricks_workspace"
    schema = database

    if not all([host, token, warehouse_id]):
        print(f"{Fore.RED}❌ Missing Databricks credentials in .env file{Style.RESET_ALL}")
        print("Required: DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH")
        sys.exit(1)

    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")

    print(f"📍 Database: {Fore.BLUE}{database}{Style.RESET_ALL}")
    print(f"🏢 Host: {Fore.BLUE}{host}{Style.RESET_ALL}")
    print(f"📊 Warehouse: {Fore.BLUE}{warehouse_id}{Style.RESET_ALL}")

    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token,
        ) as connection:
            with connection.cursor() as cursor:
                # First, query to find all tables in the schema
                print(f"\n🔍 Discovering tables in {catalog}.{schema}...")
                table_query = f"""
                SHOW TABLES IN {catalog}.{schema}
                """

                cursor.execute(table_query)
                all_tables = cursor.fetchall()

                if not all_tables:
                    print(f"⚠️  No tables found in {catalog}.{schema}")
                    print("   You may need to run the setup or check the catalog/schema names")
                    return {"icon": "❌", "text": "No tables", "latest": "N/A", "records": 0}

                print(f"Found {len(all_tables)} tables:")
                for table_info in all_tables:
                    print(f"  - {table_info[1]}")  # Table name is usually in second column

                # Query each discovered table
                results = []
                for table_info in all_tables:
                    table = table_info[1]  # Table name
                    full_table = f"{catalog}.{schema}.{table}"

                    # Check if table has expected columns
                    try:
                        # First check table schema
                        schema_query = f"DESCRIBE {full_table}"
                        cursor.execute(schema_query)
                        columns = [row[0] for row in cursor.fetchall()]

                        # Only query tables with timestamp column
                        if "timestamp" in columns:
                            # Check if we have turbine_id or sensor_id
                            id_column = (
                                "sensor_id"
                                if "sensor_id" in columns
                                else "turbine_id"
                                if "turbine_id" in columns
                                else None
                            )

                            # Get count and date range
                            if id_column:
                                query = f"""
                                SELECT 
                                    '{table}' as table_name,
                                    COUNT(*) as record_count,
                                    MIN(timestamp) as earliest_record,
                                    MAX(timestamp) as latest_record,
                                    COUNT(DISTINCT {id_column}) as unique_sensors
                                FROM {full_table}
                                """
                            else:
                                # No ID column, just get basic stats
                                query = f"""
                                SELECT 
                                    '{table}' as table_name,
                                    COUNT(*) as record_count,
                                    MIN(timestamp) as earliest_record,
                                    MAX(timestamp) as latest_record,
                                    0 as unique_sensors
                                FROM {full_table}
                                """

                            cursor.execute(query)
                            row = cursor.fetchone()
                            if row:
                                results.append(row)
                        else:
                            # Table doesn't have expected schema
                            results.append((table, 0, "No timestamp column", "", 0))
                    except Exception as e:
                        # Error querying table
                        results.append((table, 0, f"Error: {str(e)[:20]}", "", 0))

                # Display results in a nice table with freshness indicators
                print(f"\n{Fore.YELLOW}📊 TABLE OVERVIEW{Style.RESET_ALL}")

                # Add status column to results
                enhanced_results = []
                for row in results:
                    status_icon, status_text = check_data_freshness(
                        row[3] if len(row) > 3 else None
                    )
                    enhanced_row = list(row) + [f"{status_icon} {status_text}"]
                    enhanced_results.append(enhanced_row)

                headers = [
                    "Table",
                    "Records",
                    "Earliest Reading",
                    "Latest Reading (UTC)",
                    "Sensors",
                    "Status",
                ]
                print(tabulate(enhanced_results, headers=headers, tablefmt="grid"))

                # Get total summary only if we have results
                if results and any(r[1] > 0 for r in results):
                    print(f"\n{Fore.GREEN}📊 OVERALL SUMMARY{Style.RESET_ALL}")

                    # Build dynamic UNION query based on existing tables with data
                    union_parts = []
                    for r in results:
                        if r[1] > 0 and "Error" not in str(r[2]):  # Has records and no error
                            # Check which ID column exists in this table
                            schema_query = f"DESCRIBE {catalog}.{schema}.{r[0]}"
                            cursor.execute(schema_query)
                            columns = [row[0] for row in cursor.fetchall()]
                            id_col = (
                                "sensor_id"
                                if "sensor_id" in columns
                                else "turbine_id"
                                if "turbine_id" in columns
                                else "'unknown'"
                            )

                            union_parts.append(f"""
                                SELECT '{r[0]}' as stage, timestamp, {id_col} as sensor_id 
                                FROM {catalog}.{schema}.{r[0]}
                            """)

                    if union_parts:
                        query = f"""
                        WITH all_data AS (
                            {" UNION ALL ".join(union_parts)}
                        )
                        SELECT 
                            COUNT(*) as total_records,
                            COUNT(DISTINCT sensor_id) as total_sensors,
                            MIN(timestamp) as earliest_data,
                            MAX(timestamp) as latest_data,
                            COUNT(DISTINCT DATE(timestamp)) as days_of_data
                        FROM all_data
                        """

                        try:
                            cursor.execute(query)
                            row = cursor.fetchone()
                            if row:
                                print(f"  📈 Total Records: {Fore.CYAN}{row[0]:,}{Style.RESET_ALL}")
                                print(f"  🔢 Total Sensors: {Fore.CYAN}{row[1]}{Style.RESET_ALL}")
                                print(
                                    f"  📅 Date Range: {Fore.CYAN}{format_timestamp(row[2])} to {format_timestamp(row[3])}{Style.RESET_ALL}"
                                )
                                print(f"  📆 Days of Data: {Fore.CYAN}{row[4]}{Style.RESET_ALL}")

                                # Check overall data freshness
                                status_icon, status_text = check_data_freshness(row[3])
                                print(f"  {status_icon} Data Status: {status_text}")
                        except Exception as e:
                            print(f"Could not generate overall summary: {e}")

                # Show sample entries only for key tables
                print(f"\n{Fore.YELLOW}📋 RECENT DATA SAMPLES{Style.RESET_ALL}")
                print("-" * 70)

                # Only show samples for ingestion and aggregated tables
                key_tables = ["sensor_readings_ingestion", "sensor_readings_aggregated"]

                for r in results:
                    if r[1] > 0 and "Error" not in str(r[2]) and r[0] in key_tables:
                        table_name = r[0]
                        full_table = f"{catalog}.{schema}.{table_name}"

                        print(
                            f"\n📊 {table_name.replace('sensor_readings_', '').upper()} (Last 5 records)"
                        )

                        # Get column list for this table
                        try:
                            schema_query = f"DESCRIBE {full_table}"
                            cursor.execute(schema_query)
                            columns = [row[0] for row in cursor.fetchall()]

                            # Select key columns if they exist
                            select_cols = []
                            for col in [
                                "timestamp",
                                "sensor_id",
                                "temperature",
                                "humidity",
                                "pressure",
                                "vibration",
                                "voltage",
                                "anomaly_flag",
                                "alert_level",
                                "sensor_health",
                                "record_count",
                            ]:
                                if col in columns:
                                    select_cols.append(col)

                            if select_cols:
                                # Limit columns to avoid too wide output
                                select_cols = select_cols[:8]

                                query = f"""
                                SELECT {", ".join(select_cols)}
                                FROM {full_table}
                                ORDER BY timestamp DESC
                                LIMIT 5
                                """

                                cursor.execute(query)
                                rows = cursor.fetchall()

                                if rows:
                                    # Format timestamps for readability
                                    formatted_rows = []
                                    for row in rows:
                                        formatted_row = []
                                        for i, val in enumerate(row):
                                            if i == 0 and isinstance(
                                                val, (datetime, str)
                                            ):  # timestamp
                                                try:
                                                    if isinstance(val, str):
                                                        formatted_row.append(
                                                            val[:19]
                                                        )  # YYYY-MM-DD HH:MM:SS
                                                    else:
                                                        formatted_row.append(
                                                            val.strftime("%Y-%m-%d %H:%M:%S")
                                                        )
                                                except:
                                                    formatted_row.append(str(val)[:19])
                                            elif isinstance(val, float):
                                                formatted_row.append(f"{val:.2f}")
                                            else:
                                                formatted_row.append(val)
                                        formatted_rows.append(formatted_row)

                                    print(
                                        tabulate(
                                            formatted_rows, headers=select_cols, tablefmt="simple"
                                        )
                                    )
                                else:
                                    print("No data found")
                            else:
                                print("Table has unexpected schema")

                        except Exception as e:
                            print(f"Error querying table: {str(e)[:100]}")

                # Track latest data for status return
                latest_timestamp = None
                latest_records = 0

                # Find the ingestion table for tracking
                for r in results:
                    if "ingestion" in r[0] and r[1] > 0:
                        latest_timestamp = r[3]
                        latest_records = r[1]
                        break

                # If no ingestion table, use any table with recent data
                if not latest_timestamp:
                    for r in results:
                        if r[1] > 0 and r[3]:
                            latest_timestamp = r[3]
                            latest_records = r[1]
                            break

                # Show hourly ingestion rate
                print(f"\n{Fore.YELLOW}📈 HOURLY INGESTION RATE (Last 12 hours){Style.RESET_ALL}")
                print("-" * 70)

                # Try to get ingestion data from the ingestion table first
                ingestion_table = None
                for r in results:
                    if "ingestion" in r[0] and r[1] > 0 and "Error" not in str(r[2]):
                        ingestion_table = r[0]
                        break

                # Fall back to any table with data
                if not ingestion_table:
                    for r in results:
                        if r[1] > 0 and "Error" not in str(r[2]):
                            ingestion_table = r[0]
                            break

                if ingestion_table:
                    query = f"""
                    SELECT 
                        DATE_FORMAT(timestamp, 'yyyy-MM-dd HH:00') as hour,
                        COUNT(*) as records,
                        COUNT(DISTINCT sensor_id) as active_sensors
                    FROM {catalog}.{schema}.{ingestion_table}
                    WHERE timestamp > CURRENT_TIMESTAMP() - INTERVAL 12 HOURS
                    GROUP BY 1
                    ORDER BY 1 DESC
                    LIMIT 12
                    """

                    try:
                        cursor.execute(query)
                        rows = cursor.fetchall()
                        if rows:
                            # Add status indicators
                            enhanced_rows = []
                            for row in rows:
                                hour_str = row[0]
                                records = row[1]
                                sensors = row[2]

                                # Check if this hour has good data flow
                                if records > 100:
                                    status = "🟢 Good"
                                elif records > 10:
                                    status = "🟡 Low"
                                else:
                                    status = "🔴 Minimal"

                                enhanced_rows.append([hour_str, records, sensors, status])

                            print(
                                tabulate(
                                    enhanced_rows,
                                    headers=["Hour", "Records", "Sensors", "Status"],
                                    tablefmt="simple",
                                )
                            )
                        else:
                            print(f"{Fore.RED}⚠️  No data in the last 12 hours{Style.RESET_ALL}")
                    except Exception as e:
                        print(
                            f"{Fore.RED}Error getting hourly data: {str(e)[:50]}{Style.RESET_ALL}"
                        )

                # Return status for summary
                if latest_timestamp:
                    status_icon, status_text = check_data_freshness(latest_timestamp)
                    return {
                        "icon": status_icon,
                        "text": status_text,
                        "latest": format_timestamp(latest_timestamp),
                        "records": latest_records,
                    }
                else:
                    return {"icon": "❌", "text": "No data", "latest": "N/A", "records": 0}

    except Exception as e:
        print(f"❌ Error connecting to Databricks: {e}")
        return {"icon": "❌", "text": f"Error: {str(e)[:30]}", "latest": "N/A", "records": 0}


def query_s3_buckets():
    """Query all S3 buckets and show summary."""

    print_header("📦 S3 BUCKET SUMMARY")

    # Get AWS credentials - check multiple sources
    aws_access_key = None
    aws_secret_key = None
    aws_region = os.getenv("AWS_REGION", "us-west-2")

    # Try to load from credentials file first
    creds_file = Path("credentials/expanso-s3-env.sh")
    if creds_file.exists():
        print(f"📁 Loading credentials from: {creds_file}")
        with open(creds_file, "r") as f:
            for line in f:
                if line.startswith("export AWS_ACCESS_KEY_ID="):
                    aws_access_key = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("export AWS_SECRET_ACCESS_KEY="):
                    aws_secret_key = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("export AWS_DEFAULT_REGION="):
                    aws_region = line.split("=", 1)[1].strip().strip("'\"")

    # Fall back to environment variables
    if not aws_access_key:
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key:
        print("⚠️  No AWS credentials found. Skipping S3 query.")
        print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or")
        print("   create credentials/expanso-s3-env.sh")
        return {"icon": "❌", "text": "No credentials", "latest": "N/A"}

    # Create S3 client
    s3_client = boto3.client(
        "s3",
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
    )

    # Define buckets to check - only the ones that actually exist
    # Use actual bucket names from bucket-config.env
    bucket_names = {
        "ingestion": "expanso-raw-data-us-west-2",  # S3_BUCKET_RAW
        "validated": "expanso-validated-data-us-west-2",  # S3_BUCKET_VALIDATED
        "enriched": "expanso-schematized-data-us-west-2",  # S3_BUCKET_SCHEMATIZED
        "aggregated": "expanso-aggregated-data-us-west-2",  # S3_BUCKET_AGGREGATED
    }

    results = []
    total_files = 0
    total_size = 0
    ingestion_latest = None

    for bucket_type, bucket_name in bucket_names.items():
        try:
            # List objects in bucket
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name)

            file_count = 0
            bucket_size = 0
            latest_modified = None

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        file_count += 1
                        bucket_size += obj.get("Size", 0)
                        obj_modified = obj.get("LastModified")
                        if obj_modified and (not latest_modified or obj_modified > latest_modified):
                            latest_modified = obj_modified

            total_files += file_count
            total_size += bucket_size

            # Track ingestion bucket latest time
            if bucket_type == "ingestion" and latest_modified:
                ingestion_latest = latest_modified

            # Format size
            size_mb = bucket_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb < 1024 else f"{size_mb / 1024:.2f} GB"

            # Format date
            date_str = latest_modified.strftime("%Y-%m-%d %H:%M") if latest_modified else "N/A"

            results.append([bucket_type, file_count, size_str, date_str])

        except Exception as e:
            if "NoSuchBucket" in str(e):
                results.append([bucket_type, 0, "0 MB", "Bucket not found"])
            else:
                results.append([bucket_type, 0, "0 MB", f"Error: {str(e)[:30]}"])

    # Add freshness status to results
    enhanced_results = []
    for row in results:
        bucket_type, file_count, size_str, date_str = row

        # Parse date for freshness check
        if (
            date_str
            and date_str != "N/A"
            and "Error" not in date_str
            and "not found" not in date_str
        ):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                status_icon, status_text = check_data_freshness(dt)
            except:
                status_icon, status_text = "⚪", "Unknown"
        else:
            status_icon, status_text = "❌", date_str

        enhanced_results.append(
            [bucket_type, file_count, size_str, date_str, f"{status_icon} {status_text}"]
        )

    # Display results
    headers = ["Bucket Type", "Files", "Total Size", "Last Upload (UTC)", "Status"]
    print(tabulate(enhanced_results, headers=headers, tablefmt="grid"))

    # Show totals
    total_size_mb = total_size / (1024 * 1024)
    size_display = (
        f"{total_size_mb:.2f} MB" if total_size_mb < 1024 else f"{total_size_mb / 1024:.2f} GB"
    )
    print(
        f"\n📊 TOTALS: {Fore.CYAN}{total_files:,}{Style.RESET_ALL} files, {Fore.CYAN}{size_display}{Style.RESET_ALL}"
    )

    # Show recent uploads (last 10 files from ingestion bucket for better monitoring)
    print(f"\n{Fore.YELLOW}📤 RECENT INGESTION FILES (Last 10){Style.RESET_ALL}")

    try:
        response = s3_client.list_objects_v2(Bucket=bucket_names["ingestion"], MaxKeys=1000)

        if "Contents" in response:
            # Get all files and sort by date
            files = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)[:10]

            recent_data = []
            for obj in files:
                key = obj["Key"]
                # Extract just filename from path
                filename = key.split("/")[-1] if "/" in key else key
                size_kb = obj["Size"] / 1024
                modified = obj["LastModified"]

                # Check freshness
                status_icon, _ = check_data_freshness(modified)

                recent_data.append(
                    [
                        status_icon,
                        filename[:40] + ("..." if len(filename) > 40 else ""),
                        f"{size_kb:.1f} KB",
                        modified.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )

            print(
                tabulate(
                    recent_data, headers=["Status", "File", "Size", "Uploaded"], tablefmt="simple"
                )
            )
        else:
            print(f"{Fore.RED}No files found in ingestion bucket{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error listing recent files: {str(e)[:50]}{Style.RESET_ALL}")

    # Return status for summary
    if ingestion_latest:
        status_icon, status_text = check_data_freshness(ingestion_latest)
        return {
            "icon": status_icon,
            "text": status_text,
            "latest": ingestion_latest.strftime("%Y-%m-%d %H:%M:%S"),
        }
    else:
        return {"icon": "❌", "text": "No data", "latest": "N/A"}


def print_data_flow_summary(s3_status, db_status):
    """Print a summary of data flow status."""
    print_header("🔍 DATA FLOW STATUS SUMMARY", Fore.GREEN)

    # Print timestamp information first
    print_timestamp_info()

    # Get current UTC time for reference
    from datetime import timezone

    current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"{Fore.BLUE}⏰ Current Time: {current_utc}{Style.RESET_ALL}\n")

    # Check S3 ingestion status
    s3_icon = s3_status.get("icon", "⚪")
    s3_text = s3_status.get("text", "Unknown")
    s3_latest = s3_status.get("latest", "N/A")

    # Check DB ingestion status
    db_icon = db_status.get("icon", "⚪")
    db_text = db_status.get("text", "Unknown")
    db_latest = db_status.get("latest", "N/A")
    db_records = db_status.get("records", 0)

    print(f"{Fore.CYAN}📥 S3 UPLOADS (File Upload Time):{Style.RESET_ALL}")
    print(f"   Status: {s3_icon} {s3_text}")
    print(f"   Latest Upload: {s3_latest} UTC")

    print(f"\n{Fore.CYAN}📊 DATABRICKS DATA (Sensor Reading Time):{Style.RESET_ALL}")
    print(f"   Status: {db_icon} {db_text}")
    print(f"   Latest Reading: {db_latest} UTC")
    print(f"   Total Records: {db_records:,}")

    # Calculate lag between S3 upload and DB ingestion if both are recent
    if "LIVE" in s3_text and "LIVE" in db_text:
        try:
            s3_time = datetime.strptime(s3_latest[:19], "%Y-%m-%d %H:%M:%S")
            db_time = datetime.strptime(db_latest[:19], "%Y-%m-%dT%H:%M:%S")
            lag = abs((s3_time - db_time).total_seconds())
            if lag < 60:
                print(
                    f"\n{Fore.GREEN}⚡ Pipeline Lag: {int(lag)} seconds (S3 upload → DB ingestion){Style.RESET_ALL}"
                )
            else:
                print(
                    f"\n{Fore.YELLOW}⚡ Pipeline Lag: {int(lag / 60)} minutes (S3 upload → DB ingestion){Style.RESET_ALL}"
                )
        except:
            pass

    # Overall assessment
    print(f"\n{Fore.CYAN}🎯 OVERALL PIPELINE STATUS:{Style.RESET_ALL}")

    if "LIVE" in s3_text and "LIVE" in db_text:
        print(
            f"   {Fore.GREEN}✅ Pipeline is FULLY OPERATIONAL - Data is flowing normally{Style.RESET_ALL}"
        )
    elif "LIVE" in s3_text or "RECENT" in s3_text:
        print(
            f"   {Fore.YELLOW}⚠️  S3 uploads are active but Databricks ingestion may be delayed{Style.RESET_ALL}"
        )
    elif "LIVE" in db_text or "RECENT" in db_text:
        print(
            f"   {Fore.YELLOW}⚠️  Databricks has recent data but S3 uploads may be stopped{Style.RESET_ALL}"
        )
    else:
        print(
            f"   {Fore.RED}❌ Pipeline appears to be STOPPED - No recent data flow detected{Style.RESET_ALL}"
        )

    print(f"\n{Fore.CYAN}💡 TROUBLESHOOTING TIPS:{Style.RESET_ALL}")

    if "OLD" in s3_text or "STALE" in s3_text:
        print(f"   • Check if sensor is running: ./run.sh --mode docker --component sensor")
        print(f"   • Check if uploader is running: ./run.sh --mode docker --component uploader")

    if "OLD" in db_text or "STALE" in db_text:
        print(f"   • Check Databricks Auto Loader job status in the Databricks workspace")
        print(f"   • Verify Databricks credentials in .env file")

    print("")


if __name__ == "__main__":
    # Track status for summary
    s3_status = {}
    db_status = {}

    # Query S3 first
    try:
        # We'll need to modify query_s3_buckets to return status
        s3_status = query_s3_buckets()
    except Exception as e:
        print(f"{Fore.RED}Error querying S3: {e}{Style.RESET_ALL}")
        s3_status = {"icon": "❌", "text": "Error", "latest": "N/A"}

    # Query Databricks
    try:
        db_status = query_unity_catalog()
    except Exception as e:
        print(f"{Fore.RED}Error querying Databricks: {e}{Style.RESET_ALL}")
        db_status = {"icon": "❌", "text": "Error", "latest": "N/A", "records": 0}

    # Print final summary
    print_data_flow_summary(s3_status, db_status)
