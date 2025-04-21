#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///
import base64
import json
import os
import sys
import yaml

def validate_json_file(file_path):
    try:
        with open(file_path, 'r') as f:
            json.load(f)
        return True
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in {file_path}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return False

def validate_yaml_file(file_path):
    try:
        with open(file_path, 'r') as f:
            yaml.safe_load(f)
        return True
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML format in {file_path}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return False

try:
    # Create directory if it doesn't exist
    os.makedirs("/root", exist_ok=True)

    # Get base64 encoded file and name from environment
    file_b64 = os.environ.get('FILE_B64')
    file_name = os.environ.get('FILE_NAME')

    if not file_b64 or not file_name:
        print("Error: Missing base64 encoded file or file name in environment")
        sys.exit(1)

    # Decode and write file
    print(f"Writing {file_name}...")
    with open(f"/root/{file_name}", "wb") as f:
        f.write(base64.b64decode(file_b64))
    
    print(f"File {file_name} written successfully")
    
    # Validate file format
    print(f"Validating {file_name}...")
    if file_name.endswith('.json'):
        if not validate_json_file(f"/root/{file_name}"):
            print(f"Error: Invalid JSON format in {file_name}")
            sys.exit(1)
    elif file_name.endswith('.yaml'):
        if not validate_yaml_file(f"/root/{file_name}"):
            print(f"Error: Invalid YAML format in {file_name}")
            sys.exit(1)
    
    # List the files
    print("Files in /root:")
    for file in os.listdir("/root"):
        print(f"  - {file}")
    
    print(f"{file_name} validated successfully")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)