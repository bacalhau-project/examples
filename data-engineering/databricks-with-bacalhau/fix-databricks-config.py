#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""Fix common Databricks configuration issues."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv, set_key

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

def fix_databricks_host():
    """Fix common issues with DATABRICKS_HOST."""
    host = os.getenv('DATABRICKS_HOST', '').strip()
    original_host = host
    
    # Remove trailing slash
    if host.endswith('/'):
        host = host.rstrip('/')
    
    # Ensure it starts with https://
    if not host.startswith('https://') and host:
        host = f'https://{host}'
    
    if host != original_host:
        print(f"Fixing DATABRICKS_HOST:")
        print(f"  From: {original_host}")
        print(f"  To:   {host}")
        set_key(env_path, 'DATABRICKS_HOST', host)
        return True
    else:
        print(f"DATABRICKS_HOST is correct: {host}")
        return False

def validate_http_path():
    """Validate HTTP path format."""
    http_path = os.getenv('DATABRICKS_HTTP_PATH', '').strip()
    
    if not http_path:
        print("❌ DATABRICKS_HTTP_PATH is empty!")
        return False
    
    # Check format
    if not http_path.startswith('/sql/'):
        print(f"⚠️  DATABRICKS_HTTP_PATH might be incorrect: {http_path}")
        print("   Expected format: /sql/1.0/warehouses/xxxxx")
        return False
    
    print(f"✅ DATABRICKS_HTTP_PATH looks correct: {http_path}")
    return True

def validate_token():
    """Check if token is present."""
    token = os.getenv('DATABRICKS_TOKEN', '').strip()
    
    if not token:
        print("❌ DATABRICKS_TOKEN is empty!")
        return False
    
    if len(token) < 20:
        print("⚠️  DATABRICKS_TOKEN seems too short")
        return False
    
    print(f"✅ DATABRICKS_TOKEN is present ({len(token)} characters)")
    return True

def main():
    """Fix and validate Databricks configuration."""
    print("Checking Databricks configuration...")
    print("-" * 40)
    
    # Fix host
    host_fixed = fix_databricks_host()
    
    # Validate other settings
    http_path_ok = validate_http_path()
    token_ok = validate_token()
    
    print()
    if host_fixed:
        print("✅ Configuration fixed! Please run your script again.")
    elif http_path_ok and token_ok:
        print("✅ Configuration looks good!")
    else:
        print("❌ Configuration issues found. Please check the settings above.")
        print()
        print("To get correct values:")
        print("1. Go to Databricks UI")
        print("2. Navigate to SQL Warehouses")
        print("3. Click on your warehouse")
        print("4. Copy the 'Server hostname' (without https:// or trailing /)")
        print("5. Copy the 'HTTP path'")
        print("6. Generate a new token: User Settings > Developer > Access tokens")

if __name__ == "__main__":
    main()