#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
# ]
# ///
import base64
import json
import os
import sys
import requests

try:
    # Read the file list from environment variable
    file_list_json = os.environ.get("FILE_LIST_B64")
    if not file_list_json:
        print("Error: FILE_LIST_B64 environment variable not found")
        sys.exit(1)

    # Parse the file list
    file_list = json.loads(base64.b64decode(file_list_json))
    
    # Process each file
    for file_path, gist_url in file_list.items():
        print(f"Processing {file_path} from {gist_url}")
        
        # Download the gist content
        response = requests.get(gist_url)
        if response.status_code != 200:
            print(f"Error: Failed to download gist from {gist_url}")
            continue
            
        # Get the content
        file_contents = response.content
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write the file
        with open(file_path, "wb") as f:
            f.write(file_contents)
            
        # Verify the write
        if not os.path.exists(file_path):
            print(f"Error: Failed to write file to {file_path}")
            continue
            
        print(f"Successfully wrote file to {file_path}")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)