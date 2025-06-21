#!/usr/bin/env python3
"""
Simple test to verify the timestamp file location changes.
This test doesn't require heavy dependencies like duckdb.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
import json

# Add the bigquery-uploader directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "bigquery-uploader"))

def test_timestamp_file_location():
    """Test that timestamp file is created in the correct location with correct name"""
    print("Testing timestamp file location and naming...")

    # Create temporary test directory
    with tempfile.TemporaryDirectory(prefix="timestamp_test_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create mock log directory structure
        log_dir = temp_path / "var" / "log" / "app"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create a test log file
        log_file = log_dir / "access.log"
        log_file.write_text("test log content\n")

        # Test config pointing to the log file
        test_config = {
            'input_paths': [str(log_file)]
        }

        # Import after setting up the test environment
        try:
            from bigquery_uploader import get_timestamp_file_path, write_last_batch_timestamp, read_last_batch_timestamp
        except ImportError as e:
            print(f"❌ Failed to import: {e}")
            return False

        # Test 1: Check timestamp file path
        timestamp_path = get_timestamp_file_path(test_config)
        expected_path = log_dir / ".last_batch_timestamp.json"

        print(f"Expected path: {expected_path}")
        print(f"Actual path:   {timestamp_path}")

        assert timestamp_path == expected_path, f"❌ Path mismatch! Expected {expected_path}, got {timestamp_path}"

        print("✅ Timestamp file path is correct")

        # Test 2: Check filename starts with dot
        assert timestamp_path.name.startswith('.'), f"❌ Filename doesn't start with dot: {timestamp_path.name}"

        print("✅ Filename correctly starts with dot (hidden file)")

        # Test 3: Check file is in log directory
        assert timestamp_path.parent == log_dir, f"❌ File not in log directory: {timestamp_path.parent} != {log_dir}"

        print("✅ File is in the same directory as log files")

        # Test 4: Test with glob pattern
        glob_config = {
            'input_paths': [str(log_dir / "*.log")]
        }

        glob_timestamp_path = get_timestamp_file_path(glob_config)
        assert glob_timestamp_path == expected_path, f"❌ Glob pattern path mismatch: {glob_timestamp_path} != {expected_path}"

        print("✅ Glob pattern handling works correctly")

        # Test 5: Test fallback behavior (no config)
        fallback_path = get_timestamp_file_path()
        assert fallback_path.name.startswith('.'), f"❌ Fallback filename doesn't start with dot: {fallback_path.name}"

        print("✅ Fallback behavior maintains dot prefix")

        # Test 6: Test actual file operations
        try:
            test_timestamp = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)

            # Write timestamp
            write_last_batch_timestamp(test_timestamp, test_config)

            assert timestamp_path.exists(), f"❌ Timestamp file was not created: {timestamp_path}"

            print("✅ Timestamp file created successfully")

            # Read timestamp back
            read_timestamp = read_last_batch_timestamp(test_config)

            assert read_timestamp is not None, "❌ Failed to read timestamp back"

            assert abs((read_timestamp - test_timestamp).total_seconds()) <= 1, f"❌ Timestamp mismatch: {read_timestamp} != {test_timestamp}"

            print("✅ Timestamp read/write operations work correctly")

            # Verify file format
            with open(timestamp_path, 'r') as f:
                data = json.load(f)

            required_fields = ['last_batch_timestamp', 'last_updated', 'description']
            for field in required_fields:
                assert field in data, f"❌ Missing field in timestamp file: {field}"

            print("✅ Timestamp file format is correct")

        except Exception as e:
            print(f"❌ File operations failed: {e}")
            raise

        print("\n🎉 All tests passed!")


def test_multiple_log_paths():
    """Test behavior with multiple log paths"""
    print("\nTesting multiple log paths...")

    with tempfile.TemporaryDirectory(prefix="multi_path_test_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create multiple log directories
        log_dir1 = temp_path / "logs1"
        log_dir2 = temp_path / "logs2"
        log_dir1.mkdir()
        log_dir2.mkdir()

        # Create log files
        log_file1 = log_dir1 / "app1.log"
        log_file2 = log_dir2 / "app2.log"
        log_file1.write_text("log1 content\n")
        log_file2.write_text("log2 content\n")

        # Test config with multiple paths
        test_config = {
            'input_paths': [str(log_file1), str(log_file2)]
        }

        try:
            from bigquery_uploader import get_timestamp_file_path
        except ImportError as e:
            print(f"❌ Failed to import: {e}")
            raise

        # Should use the first path's directory
        timestamp_path = get_timestamp_file_path(test_config)
        expected_path = log_dir1 / ".last_batch_timestamp.json"

        assert timestamp_path == expected_path, f"❌ Multiple paths: expected {expected_path}, got {timestamp_path}"

        print("✅ Multiple paths: uses first path's directory correctly")


if __name__ == "__main__":
    print("Testing timestamp file location changes")
    print("=" * 50)

    test_timestamp_file_location()
    test_multiple_log_paths()

    print("\n🎉 All location tests passed!")
    print("✅ Timestamp file is now:")
    print("   - Hidden (starts with dot)")
    print("   - Located in same directory as log files")
    print("   - Works with both single files and glob patterns")
