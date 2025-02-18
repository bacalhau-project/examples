#!/bin/bash
set -e

# Check if credentials file exists
if [ ! -f "log_uploader_credentials.json" ]; then
    echo "Error: log_uploader_credentials.json not found in current directory"
    exit 1
fi

# Check if config file exists
if [ ! -f "../config.yaml" ]; then
    echo "Error: config.yaml not found in parent directory"
    exit 1
fi

# Read and encode the credentials
echo "Reading and encoding credentials..."
CREDS_B64=$(base64 -i log_uploader_credentials.json)

# Read and encode the PostgreSQL connection info
echo "Reading and encoding PostgreSQL connection info..."
PG_CONFIG_B64=$(yq e '.postgresql' ../config.yaml | base64)

# Create and encode the Python script directly in memory
SCRIPT_B64=$(cat << 'EOF' | base64
#!/usr/bin/env python3
import base64
import os
import stat
import sys
import yaml

try:
    # Get the credentials and config from environment variables
    creds_b64 = os.environ.get('CREDS_B64')
    pg_config_b64 = os.environ.get('PG_CONFIG_B64')
    
    if not creds_b64:
        print("Error: CREDS_B64 environment variable not found")
        sys.exit(1)
    
    if not pg_config_b64:
        print("Error: PG_CONFIG_B64 environment variable not found")
        sys.exit(1)

    # Create the target directory if it doesn't exist
    target_dir = '/var/log/logs_to_process'
    os.makedirs(target_dir, exist_ok=True)

    # Write the credentials
    creds_path = os.path.join(target_dir, 'log_uploader_credentials.json')
    with open(creds_path, 'wb') as f:
        f.write(base64.b64decode(creds_b64))
    
    # Set permissions to be readable only by owner (600)
    os.chmod(creds_path, stat.S_IRUSR | stat.S_IWUSR)

    # Decode and parse the PostgreSQL config
    pg_config = yaml.safe_load(base64.b64decode(pg_config_b64))
    
    # Verify all required fields are present
    required_fields = ['database', 'user', 'password', 'host', 'port']
    missing_fields = [field for field in required_fields if field not in pg_config]
    
    if missing_fields:
        print(f"Error: Missing required PostgreSQL config fields: {', '.join(missing_fields)}")
        sys.exit(1)
    
    # Write the connection info
    conn_path = os.path.join(target_dir, 'connection_info.yaml')
    with open(conn_path, 'w') as f:
        yaml.dump({'postgresql': pg_config}, f)
    
    # Set permissions to be readable only by owner (600)
    os.chmod(conn_path, stat.S_IRUSR | stat.S_IWUSR)

    # Verify the writes
    for path in [creds_path, conn_path]:
        if not os.path.exists(path):
            print(f"Error: Failed to write file: {path}")
            sys.exit(1)
        
        perms = oct(os.stat(path).st_mode)[-3:]
        if perms != '600':
            print(f"Warning: Unexpected permissions for {path}: {perms}")
            sys.exit(1)

    print(f"Successfully wrote credentials to {creds_path}")
    print(f"Successfully wrote connection info to {conn_path}")
    print("File permissions: 600")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
EOF
)

echo "Distributing credentials and connection info to all nodes..."
bacalhau docker run \
    -e SCRIPT_B64="$SCRIPT_B64" \
    -e CREDS_B64="$CREDS_B64" \
    -e PG_CONFIG_B64="$PG_CONFIG_B64" \
    -e DEBUG=true \
    --target all \
    --input file:///bacalhau_data,dst=/var/log/logs_to_process,opt=readwrite=true \
    python:3.11-slim \
    -- /bin/bash -c 'echo "$SCRIPT_B64" | base64 -d > /tmp/write_files.py && python /tmp/write_files.py'

echo "Credentials and connection info distribution complete."