#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "python-dotenv",
# ]
# ///

"""Debug Databricks connection using REST API."""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

def test_rest_api():
    """Test Databricks REST API connection."""
    host = os.getenv('DATABRICKS_HOST', '').strip()
    token = os.getenv('DATABRICKS_TOKEN', '').strip()
    
    print("Testing Databricks REST API...")
    print("-" * 40)
    print(f"Host: {host}")
    print(f"Token: {'*' * 10}...{token[-4:] if len(token) > 4 else '****'}")
    print()
    
    if not all([host, token]):
        print("❌ Missing required environment variables!")
        return False
    
    # Test API endpoint
    url = f"{host}/api/2.0/clusters/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing endpoint: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API connection successful!")
            data = response.json()
            if 'clusters' in data:
                print(f"Found {len(data['clusters'])} clusters")
            return True
        elif response.status_code == 401:
            print("❌ Authentication failed - token is invalid or expired")
            print("Please generate a new token in Databricks UI")
        elif response.status_code == 403:
            print("❌ Permission denied - token lacks required permissions")
        else:
            print(f"❌ Unexpected response: {response.text[:200]}")
        
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Connection timed out")
        print("Possible issues:")
        print("- Network/firewall blocking connection")
        print("- Databricks workspace URL is incorrect")
        print("- VPN required to access Databricks")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_sql_endpoint():
    """Test SQL endpoint availability."""
    host = os.getenv('DATABRICKS_HOST', '').strip()
    token = os.getenv('DATABRICKS_TOKEN', '').strip()
    
    print("\nTesting SQL endpoints...")
    print("-" * 40)
    
    url = f"{host}/api/2.0/sql/warehouses"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            warehouses = data.get('warehouses', [])
            print(f"✅ Found {len(warehouses)} SQL warehouses")
            
            for wh in warehouses:
                print(f"  - {wh.get('name')} ({wh.get('state')})")
                print(f"    ID: {wh.get('id')}")
                print(f"    HTTP Path: /sql/1.0/warehouses/{wh.get('id')}")
                if wh.get('state') != 'RUNNING':
                    print(f"    ⚠️  Warehouse is not running!")
            
            return True
        else:
            print(f"❌ Failed to list warehouses: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to check SQL endpoints: {e}")
        return False

if __name__ == "__main__":
    api_ok = test_rest_api()
    sql_ok = test_sql_endpoint() if api_ok else False
    
    print("\n" + "=" * 40)
    if api_ok and sql_ok:
        print("✅ Databricks connectivity verified!")
        print("\nIf SQL connector still hangs, try:")
        print("1. Restart the SQL warehouse in Databricks UI")
        print("2. Check if warehouse is in RUNNING state")
        print("3. Generate a new access token")
    else:
        print("❌ Connection issues detected")
        print("\nPlease fix the issues above and try again")
    
    sys.exit(0 if api_ok else 1)