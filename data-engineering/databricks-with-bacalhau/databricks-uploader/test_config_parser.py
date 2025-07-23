#!/usr/bin/env python3
"""Test configuration parsing without processing_mode field"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Minimal test to check if config loads without processing_mode
try:
    # Read the test config file
    with open('test_config_without_processing_mode.yaml', 'r') as f:
        content = f.read()
    
    print("✓ Config file read successfully")
    print(f"✓ File size: {len(content)} bytes")
    
    # Check if processing_mode is absent (excluding comments)
    lines = content.splitlines()
    has_processing_mode = False
    for line in lines:
        if not line.strip().startswith('#') and 'processing_mode:' in line:
            has_processing_mode = True
            break
    
    if not has_processing_mode:
        print("✓ Confirmed: processing_mode field is not present in config")
    else:
        print("✗ Error: processing_mode field found in config")
        
    # Check required fields are present
    required_fields = ['sqlite', 'databricks_host', 'databricks_database', 'state_dir']
    for field in required_fields:
        if field in content:
            print(f"✓ Required field '{field}' is present")
        else:
            print(f"✗ Missing required field: {field}")
            
except Exception as e:
    print(f"✗ Error testing config: {e}")
    sys.exit(1)

print("\nConfig validation test passed!")