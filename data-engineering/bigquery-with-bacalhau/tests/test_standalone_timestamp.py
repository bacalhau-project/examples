#!/usr/bin/env python3
"""
Standalone test for timestamp path functions without heavy dependencies.
This extracts just the timestamp path logic to test the changes.
"""

import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Dict, Any, Optional


def get_timestamp_file_path(config: Optional[Dict[str, Any]] = None) -> Path:
    """Get the path to the timestamp tracking file"""
    if config and config.get('input_paths'):
        # Get the first input path and use its directory
        first_input_path = config['input_paths'][0]
        # Handle glob patterns by taking the directory part
        if '*' in first_input_path or '?' in first_input_path:
            # Extract directory from glob pattern, handling ** patterns
            path_obj = Path(first_input_path)
            # Find the first part without wildcards
            parts = path_obj.parts
            clean_parts = []
            for part in parts:
                if '*' in part or '?' in part:
                    break
                clean_parts.append(part)
            if clean_parts:
                log_dir = Path(*clean_parts)
            else:
                # If pattern starts with wildcard, use current directory
                log_dir = Path('.')
        else:
            # Regular file path
            log_dir = Path(first_input_path).parent
        return log_dir / ".last_batch_timestamp.json"
    else:
        # Fallback to current behavior for backward compatibility
        script_dir = Path(__file__).parent
        return script_dir / ".last_batch_timestamp.json"


def write_last_batch_timestamp(timestamp: datetime, config: Optional[Dict[str, Any]] = None):
    """Write the last batch timestamp to the tracking file"""
    timestamp_file = get_timestamp_file_path(config)

    # Ensure directory exists
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'last_batch_timestamp': timestamp.isoformat(),
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'description': 'Tracks the latest log timestamp processed to prevent duplicate uploads'
    }

    with open(timestamp_file, 'w') as f:
        json.dump(data, f, indent=2)


def read_last_batch_timestamp(config: Optional[Dict[str, Any]] = None) -> Optional[datetime]:
    """Read the last batch timestamp from the tracking file"""
    timestamp_file = get_timestamp_file_path(config)

    if not timestamp_file.exists():
        return None

    with open(timestamp_file, 'r') as f:
        data = json.load(f)

    timestamp_str = data.get('last_batch_timestamp')
    if timestamp_str:
        # Parse ISO format timestamp
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    else:
        return None


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

        # Test 7: Show file contents
        print("\n📋 Sample timestamp file contents:")
        print(json.dumps(data, indent=2))

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

        # Should use the first path's directory
        timestamp_path = get_timestamp_file_path(test_config)
        expected_path = log_dir1 / ".last_batch_timestamp.json"

        assert timestamp_path == expected_path, f"❌ Multiple paths: expected {expected_path}, got {timestamp_path}"

        print("✅ Multiple paths: uses first path's directory correctly")


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\nTesting edge cases...")

    # Test with empty config
    empty_config = {}
    path = get_timestamp_file_path(empty_config)
    assert path.name.startswith('.'), "❌ Empty config should fall back to dot prefix"
    print("✅ Empty config falls back correctly")

    # Test with empty input_paths
    empty_paths_config = {'input_paths': []}
    path = get_timestamp_file_path(empty_paths_config)
    assert path.name.startswith('.'), "❌ Empty input_paths should fall back to dot prefix"
    print("✅ Empty input_paths falls back correctly")

    # Test with relative paths
    relative_config = {'input_paths': ['./logs/app.log']}
    path = get_timestamp_file_path(relative_config)
    expected_name = ".last_batch_timestamp.json"
    assert path.name == expected_name, f"❌ Relative path should still produce correct filename: {path.name}"
    print("✅ Relative paths work correctly")

    # Test with complex glob patterns
    complex_glob_config = {'input_paths': ['/var/log/**/*.log']}
    path = get_timestamp_file_path(complex_glob_config)
    assert path.parent == Path('/var/log'), f"❌ Complex glob should extract correct directory: {path.parent}"
    print("✅ Complex glob patterns work correctly")

    print("✅ Complex glob patterns work correctly")


if __name__ == "__main__":
    print("Testing timestamp file location changes (standalone)")
    print("=" * 60)

    test_timestamp_file_location()
    test_multiple_log_paths()
    test_edge_cases()

    print("\n🎉 All location tests passed!")
    print("\n✅ Changes implemented:")
    print("   - Timestamp file is now hidden (starts with dot)")
    print("   - File is located in same directory as log files")
    print("   - Works with single files, multiple files, and glob patterns")
    print("   - Maintains backward compatibility with fallback behavior")
    print("   - Filename changed from 'last_batch_timestamp.json' to '.last_batch_timestamp.json'")
    print("   - File location changed from script directory to log file directory")
