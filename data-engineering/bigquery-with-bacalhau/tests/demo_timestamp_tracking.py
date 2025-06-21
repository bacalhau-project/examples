#!/usr/bin/env uv run -s
# /// script
# dependencies = [
#     "PyYAML",
#     "duckdb",
#     "pandas",
#     "google-cloud-bigquery",
#     "pyarrow",
#     "pandas-gbq",
# ]
# ///
"""
Demo script showing timestamp tracking functionality in action.
This demonstrates how the system prevents duplicate log processing.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

# Add the bigquery-uploader directory to the path so we can import the main module
sys.path.insert(0, str(Path(__file__).parent.parent / "bigquery-uploader"))

def create_demo_logs(log_dir: Path, start_time: datetime, count: int = 10):
    """Create demo log files with timestamps"""
    log_file = log_dir / "demo.log"

    entries = []
    current_time = start_time

    for i in range(count):
        # Format timestamp for Apache log format
        timestamp_str = current_time.strftime('[%d/%b/%Y:%H:%M:%S %z]')
        # Fix timezone format (remove colon): +00:00 -> +0000
        if len(timestamp_str) >= 4 and timestamp_str[-4] == ':':
            timestamp_str = timestamp_str[:-4] + timestamp_str[-3:]

        entry = f'192.168.1.{i+1} - - {timestamp_str} "GET /page{i}.html HTTP/1.1" 200 {1000 + i*100}'
        entries.append(entry)

        # Increment time by 30 minutes for each entry
        current_time += timedelta(minutes=30)

    with open(log_file, 'w') as f:
        for entry in entries:
            f.write(entry + '\n')

    return log_file, current_time - timedelta(minutes=30)  # Return last timestamp

def simulate_timestamp_tracking():
    """Simulate the timestamp tracking functionality"""
    print("🚀 BigQuery Log Processor - Timestamp Tracking Demo")
    print("=" * 60)

    # Create temporary directory for demo
    temp_dir = Path(tempfile.mkdtemp(prefix="timestamp_demo_"))
    original_cwd = os.getcwd()

    try:
        # Change to temp directory to isolate timestamp file
        os.chdir(temp_dir)

        # Import after changing directory so timestamp file is created here
        from bigquery_uploader import (
            read_last_batch_timestamp,
            write_last_batch_timestamp,
            get_timestamp_file_path,
            format_timestamp_for_duckdb
        )

        # Create test config
        test_config = {
            'input_paths': [str(log_dir / "demo.log")]
        }

        print(f"📁 Working in temporary directory: {temp_dir}")
        print(f"📄 Timestamp file will be: {get_timestamp_file_path(test_config)}")
        print()

        # Scenario 1: First run (no timestamp file exists)
        print("📋 SCENARIO 1: First run - no previous timestamp")
        print("-" * 40)

        last_timestamp = read_last_batch_timestamp(test_config)
        if last_timestamp is None:
            print("✅ No previous timestamp found - will process all logs")
        else:
            print(f"❌ Unexpected: found timestamp {last_timestamp}")
        print()

        # Create initial log batch
        log_dir = temp_dir / "logs"
        log_dir.mkdir()

        start_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        log_file, last_log_time = create_demo_logs(log_dir, start_time, 5)

        print(f"📝 Created demo logs from {start_time.strftime('%Y-%m-%d %H:%M')} to {last_log_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"📂 Log file: {log_file}")

        # Show log contents
        print("\n📖 Log contents:")
        with open(log_file, 'r') as f:
            for i, line in enumerate(f, 1):
                print(f"   {i}: {line.strip()}")
        print()

        # Simulate processing first batch
        print("⚙️  Simulating first batch processing...")
        batch_1_max_time = start_time + timedelta(hours=1, minutes=30)  # Simulate processing first 4 entries
        write_last_batch_timestamp(batch_1_max_time, test_config)
        print(f"✅ Processed first batch, last timestamp: {batch_1_max_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print()

        # Scenario 2: Second run (with existing timestamp)
        print("📋 SCENARIO 2: Second run - with previous timestamp")
        print("-" * 40)

        last_timestamp = read_last_batch_timestamp(test_config)
        print(f"📅 Found previous timestamp: {last_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Show what would be filtered
        apache_format = format_timestamp_for_duckdb(last_timestamp)
        print(f"🔍 Will filter logs newer than: {apache_format}")

        # Show which logs would be processed
        print("\n📊 Analysis of existing logs:")
        with open(log_file, 'r') as f:
            for i, line in enumerate(f, 1):
                # Extract timestamp from log line
                parts = line.split(' ')
                if len(parts) >= 4:
                    log_timestamp_str = parts[3] + ' ' + parts[4]  # [timestamp] [timezone]
                    log_timestamp_str = log_timestamp_str.strip('[]')

                    try:
                        from bigquery_uploader import parse_timestamp
                        log_timestamp = parse_timestamp('[' + log_timestamp_str + ']')

                        if log_timestamp and log_timestamp > last_timestamp:
                            status = "🟢 WOULD PROCESS"
                        else:
                            status = "🔴 WOULD SKIP"
                    except:
                        status = "❓ PARSE ERROR"
                else:
                    status = "❓ INVALID FORMAT"

                print(f"   {i}: {status} - {line.strip()}")
        print()

        # Add more logs to simulate new data
        print("📝 Adding new log entries (simulating new data arrival)...")
        new_start_time = last_log_time + timedelta(minutes=30)
        new_entries = []

        for i in range(3):  # Add 3 more entries
            current_time = new_start_time + timedelta(minutes=30 * i)
            timestamp_str = current_time.strftime('[%d/%b/%Y:%H:%M:%S %z]')
            # Fix timezone format (remove colon): +00:00 -> +0000
            if len(timestamp_str) >= 4 and timestamp_str[-4] == ':':
                timestamp_str = timestamp_str[:-4] + timestamp_str[-3:]

            entry = f'192.168.1.{10+i} - - {timestamp_str} "GET /newpage{i}.html HTTP/1.1" 200 {2000 + i*100}'
            new_entries.append(entry)

        # Append new entries to log file
        with open(log_file, 'a') as f:
            for entry in new_entries:
                f.write(entry + '\n')

        print(f"✅ Added {len(new_entries)} new log entries")
        print()

        # Show updated analysis
        print("📊 Updated analysis after new logs added:")
        with open(log_file, 'r') as f:
            for i, line in enumerate(f, 1):
                parts = line.split(' ')
                if len(parts) >= 4:
                    log_timestamp_str = parts[3] + ' ' + parts[4]
                    log_timestamp_str = log_timestamp_str.strip('[]')

                    try:
                        from bigquery_uploader import parse_timestamp
                        log_timestamp = parse_timestamp('[' + log_timestamp_str + ']')

                        if log_timestamp and log_timestamp > last_timestamp:
                            status = "🟢 WOULD PROCESS"
                        else:
                            status = "🔴 WOULD SKIP"
                    except:
                        status = "❓ PARSE ERROR"
                else:
                    status = "❓ INVALID FORMAT"

                print(f"   {i}: {status} - {line.strip()}")
        print()

        # Simulate processing second batch
        print("⚙️  Simulating second batch processing...")
        batch_2_max_time = new_start_time + timedelta(hours=1)  # Process the new entries
        write_last_batch_timestamp(batch_2_max_time, test_config)
        print(f"✅ Processed second batch, updated timestamp: {batch_2_max_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print()

        # Show timestamp file contents
        print("📋 Final timestamp file contents:")
        timestamp_file = get_timestamp_file_path(test_config)
        if timestamp_file.exists():
            with open(timestamp_file, 'r') as f:
                data = json.load(f)

            print(json.dumps(data, indent=2))
        print()

        # Summary
        print("📈 SUMMARY")
        print("-" * 40)
        print("✅ Demonstrated timestamp tracking prevents duplicate processing")
        print("✅ Old logs are automatically skipped on subsequent runs")
        print("✅ Only new logs (timestamp > last processed) are processed")
        print("✅ Timestamp file maintains state between runs")
        print("✅ System handles both first-run and incremental scenarios")

    finally:
        # Cleanup
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up temporary directory: {temp_dir}")

if __name__ == "__main__":
    try:
        simulate_timestamp_tracking()
        print("\n🎉 Demo completed successfully!")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
