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
Test script for timestamp tracking functionality in the BigQuery uploader.
This script validates that the timestamp tracking system works correctly.
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

try:
    from bigquery_uploader import (
        read_last_batch_timestamp,
        write_last_batch_timestamp,
        get_timestamp_file_path,
        format_timestamp_for_duckdb,
        get_max_timestamp_from_chunk,
        parse_timestamp
    )
    import pandas as pd
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this from the bigquery-uploader directory")
    sys.exit(1)


def test_timestamp_file_operations():
    """Test basic timestamp file read/write operations"""
    print("Testing timestamp file operations...")

    # Create test config
    test_config = {
        'input_paths': ['/tmp/test_logs/access.log']
    }

    # Clean up any existing timestamp file
    timestamp_file = get_timestamp_file_path(test_config)
    if timestamp_file.exists():
        backup_path = timestamp_file.with_suffix('.bak')
        shutil.move(timestamp_file, backup_path)
        print(f"Backed up existing timestamp file to {backup_path}")

    try:
        # Ensure the log directory exists
        log_dir = Path('/tmp/test_logs')
        log_dir.mkdir(parents=True, exist_ok=True)

        # Test reading when no file exists
        result = read_last_batch_timestamp(test_config)
        assert result is None, "Should return None when no timestamp file exists"
        print("✅ Correctly handled missing timestamp file")

        # Test writing and reading a timestamp
        test_timestamp = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        write_last_batch_timestamp(test_timestamp, test_config)
        print("✅ Successfully wrote timestamp to file")

        # Test reading the timestamp back
        read_timestamp = read_last_batch_timestamp(test_config)
        assert read_timestamp is not None, "Should read back the timestamp"
        assert abs((read_timestamp - test_timestamp).total_seconds()) < 1, "Timestamps should match"
        print("✅ Successfully read timestamp from file")

        # Test the file format
        with open(timestamp_file, 'r') as f:
            data = json.load(f)

        assert 'last_batch_timestamp' in data, "File should contain last_batch_timestamp"
        assert 'last_updated' in data, "File should contain last_updated"
        assert 'description' in data, "File should contain description"
        print("✅ Timestamp file has correct format")

        # Verify the file is in the correct location and has the right name
        assert timestamp_file.name == '.last_batch_timestamp.json', "File should be hidden with dot prefix"
        assert timestamp_file.parent == Path('/tmp/test_logs'), "File should be in log directory"
        print("✅ Timestamp file is in correct location with correct name")

    finally:
        # Clean up test file
        if timestamp_file.exists():
            timestamp_file.unlink()

        # Clean up test directory
        log_dir = Path('/tmp/test_logs')
        if log_dir.exists():
            shutil.rmtree(log_dir)

        # Restore backup if it exists
        backup_path = timestamp_file.with_suffix('.bak')
        if backup_path.exists():
            shutil.move(backup_path, timestamp_file)
            print(f"Restored backup timestamp file")


def test_apache_timestamp_formatting():
    """Test Apache log timestamp formatting"""
    print("\nTesting Apache timestamp formatting...")

    # Test various timestamps
    test_cases = [
        (datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc), "[15/Jan/2024:12:30:45 +0000]"),
        (datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=-5))), "[31/Dec/2024:23:59:59 -0500]"),
        (datetime(2024, 6, 1, 8, 15, 30, tzinfo=timezone(timedelta(hours=2))), "[01/Jun/2024:08:15:30 +0200]"),
    ]

    for timestamp, expected in test_cases:
        result = format_timestamp_for_duckdb(timestamp)
        assert result == expected, f"Expected {expected}, got {result}"
        print(f"✅ Correctly formatted {timestamp.isoformat()} -> {result}")


def test_timestamp_parsing():
    """Test parsing Apache log timestamps"""
    print("\nTesting timestamp parsing...")

    test_cases = [
        "[15/Jan/2024:12:30:45 +0000]",
        "[31/Dec/2023:23:59:59 -0500]",
        "[01/Jun/2024:08:15:30 +0200]",
        "-",  # Should return None
        "",   # Should return None
    ]

    for test_input in test_cases:
        result = parse_timestamp(test_input)
        if test_input in ["-", ""]:
            assert result is None, f"Should return None for {test_input}"
            print(f"✅ Correctly handled invalid timestamp: {test_input}")
        else:
            assert result is not None, f"Should parse valid timestamp: {test_input}"
            assert result.tzinfo is not None, "Parsed timestamp should be timezone-aware"
            print(f"✅ Successfully parsed {test_input} -> {result.isoformat()}")


def test_max_timestamp_extraction():
    """Test extracting maximum timestamp from DataFrame chunks"""
    print("\nTesting maximum timestamp extraction...")

    # Create test DataFrame with timestamps
    test_data = {
        'timestamp': [
            datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),  # This should be max
            datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        ],
        'other_column': ['a', 'b', 'c', 'd']
    }
    df = pd.DataFrame(test_data)

    max_timestamp = get_max_timestamp_from_chunk(df)
    expected = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    assert max_timestamp == expected, f"Expected {expected}, got {max_timestamp}"
    print("✅ Correctly extracted maximum timestamp from DataFrame")

    # Test with empty DataFrame
    empty_df = pd.DataFrame()
    result = get_max_timestamp_from_chunk(empty_df)
    assert result is None, "Should return None for empty DataFrame"
    print("✅ Correctly handled empty DataFrame")

    # Test with DataFrame without timestamp column
    no_timestamp_df = pd.DataFrame({'other_column': ['a', 'b', 'c']})
    result = get_max_timestamp_from_chunk(no_timestamp_df)
    assert result is None, "Should return None for DataFrame without timestamp column"
    print("✅ Correctly handled DataFrame without timestamp column")


def test_timestamp_comparison_logic():
    """Test the logic for comparing timestamps in filtering"""
    print("\nTesting timestamp comparison logic...")

    # Test that our formatting is compatible with string comparison
    base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    later_time = base_time + timedelta(hours=1)
    earlier_time = base_time - timedelta(hours=1)

    base_formatted = format_timestamp_for_duckdb(base_time)
    later_formatted = format_timestamp_for_duckdb(later_time)
    earlier_formatted = format_timestamp_for_duckdb(earlier_time)

    # String comparison should work correctly for filtering
    assert later_formatted > base_formatted, "Later timestamp should be greater in string comparison"
    assert earlier_formatted < base_formatted, "Earlier timestamp should be less in string comparison"
    print("✅ Timestamp string comparison works correctly for filtering")


def create_test_log_data():
    """Create sample log data for testing"""
    print("\nCreating test log data...")

    # Create test directory
    test_dir = Path("test_logs")
    test_dir.mkdir(exist_ok=True)

    # Sample Apache log entries with different timestamps
    log_entries = [
        '192.168.1.1 - - [15/Jan/2024:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1234',
        '192.168.1.2 - - [15/Jan/2024:11:15:30 +0000] "GET /about.html HTTP/1.1" 200 5678',
        '192.168.1.3 - - [15/Jan/2024:12:00:15 +0000] "POST /api/data HTTP/1.1" 201 9012',
        '192.168.1.4 - - [15/Jan/2024:12:45:00 +0000] "GET /contact.html HTTP/1.1" 200 3456',
        '192.168.1.5 - - [15/Jan/2024:13:30:30 +0000] "DELETE /api/resource HTTP/1.1" 204 0',
    ]

    # Write to test log file
    log_file = test_dir / "test.log"
    with open(log_file, 'w') as f:
        for entry in log_entries:
            f.write(entry + '\n')

    print(f"✅ Created test log file with {len(log_entries)} entries: {log_file}")
    return test_dir


def cleanup_test_data(test_dir):
    """Clean up test data"""
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print(f"✅ Cleaned up test directory: {test_dir}")


def run_all_tests():
    """Run all tests"""
    print("Starting timestamp tracking tests...")
    print("=" * 50)

    try:
        test_timestamp_file_operations()
        test_apache_timestamp_formatting()
        test_timestamp_parsing()
        test_max_timestamp_extraction()
        test_timestamp_comparison_logic()

        print("\n" + "=" * 50)
        print("🎉 All timestamp tracking tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
