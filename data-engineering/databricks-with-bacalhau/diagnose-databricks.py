#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0"
# ]
# ///
"""Diagnose Databricks connection issues"""

import os
import requests
import time
from dotenv import load_dotenv
from rich.console import Console
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

console = Console()

def test_databricks_api():
    """Test Databricks REST API connection"""
    
    host = os.getenv('DATABRICKS_HOST').rstrip('/')
    token = os.getenv('DATABRICKS_TOKEN')
    
    console.print(f"[yellow]Testing Databricks API...[/yellow]")
    console.print(f"Host: {host}")
    
    # Test basic API endpoint
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Try to list clusters
    try:
        console.print("\n[yellow]1. Testing API connectivity...[/yellow]")
        response = requests.get(
            f"{host}/api/2.0/clusters/list",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            console.print("[green]✓ API connection successful[/green]")
            data = response.json()
            console.print(f"[cyan]Found {len(data.get('clusters', []))} clusters[/cyan]")
        elif response.status_code == 403:
            console.print("[red]✗ Authentication failed - check token[/red]")
        else:
            console.print(f"[red]✗ API error: {response.status_code} - {response.text}[/red]")
            
    except requests.exceptions.Timeout:
        console.print("[red]✗ Connection timeout - check network/firewall[/red]")
    except Exception as e:
        console.print(f"[red]✗ Connection error: {e}[/red]")
    
    # Test SQL endpoint
    try:
        console.print("\n[yellow]2. Testing SQL endpoint...[/yellow]")
        http_path = os.getenv('DATABRICKS_HTTP_PATH')
        
        # Parse warehouse ID from HTTP path
        warehouse_id = http_path.split('/')[-1] if http_path else None
        console.print(f"Warehouse ID: {warehouse_id}")
        
        if warehouse_id:
            # Check warehouse status
            response = requests.get(
                f"{host}/api/2.0/sql/warehouses/{warehouse_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                warehouse = response.json()
                state = warehouse.get('state', 'UNKNOWN')
                console.print(f"[cyan]Warehouse state: {state}[/cyan]")
                
                if state == 'RUNNING':
                    console.print("[green]✓ SQL warehouse is running[/green]")
                elif state == 'STOPPED':
                    console.print("[yellow]⚠ SQL warehouse is stopped - start it in Databricks UI[/yellow]")
                else:
                    console.print(f"[yellow]⚠ SQL warehouse state: {state}[/yellow]")
            else:
                console.print(f"[red]✗ Cannot check warehouse: {response.status_code}[/red]")
                
    except Exception as e:
        console.print(f"[red]✗ SQL endpoint error: {e}[/red]")
    
    # Test with curl command
    console.print("\n[yellow]3. Alternative test with curl:[/yellow]")
    curl_cmd = f"""curl -X GET \\
  {host}/api/2.0/clusters/list \\
  -H 'Authorization: Bearer {token[:10]}...' \\
  -H 'Content-Type: application/json'"""
    
    console.print(f"[dim]{curl_cmd}[/dim]")
    
    return True

def check_network():
    """Check network connectivity"""
    console.print("\n[yellow]4. Checking network connectivity...[/yellow]")
    
    host = os.getenv('DATABRICKS_HOST')
    parsed = urlparse(host)
    hostname = parsed.hostname
    
    # Try to resolve hostname
    import socket
    try:
        ip = socket.gethostbyname(hostname)
        console.print(f"[green]✓ DNS resolution: {hostname} → {ip}[/green]")
    except:
        console.print(f"[red]✗ Cannot resolve hostname: {hostname}[/red]")
        return False
    
    # Try to connect to port 443
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((hostname, 443))
        sock.close()
        
        if result == 0:
            console.print(f"[green]✓ Can connect to {hostname}:443[/green]")
        else:
            console.print(f"[red]✗ Cannot connect to {hostname}:443[/red]")
            console.print("[yellow]Check firewall/proxy settings[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Network error: {e}[/red]")
    
    return True

def suggest_alternatives():
    """Suggest alternative approaches"""
    console.print("\n[cyan]=== Alternative Approaches ===[/cyan]")
    
    console.print("\n[yellow]Option 1: Use Databricks Web UI[/yellow]")
    console.print("1. Log into Databricks workspace")
    console.print("2. Create new SQL notebook")
    console.print("3. Copy/paste SQL from setup-autoloader-tables.sql")
    console.print("4. Run all cells")
    
    console.print("\n[yellow]Option 2: Use Databricks CLI[/yellow]")
    console.print("```bash")
    console.print("# Install Databricks CLI")
    console.print("pip install databricks-cli")
    console.print("")
    console.print("# Configure")
    console.print("databricks configure --token")
    console.print("")
    console.print("# Run SQL file")
    console.print("databricks sql execute --sql-file databricks-notebooks/setup-autoloader-tables.sql")
    console.print("```")
    
    console.print("\n[yellow]Option 3: Check if tables already exist[/yellow]")
    console.print("In Databricks SQL Editor, run:")
    console.print("```sql")
    console.print("SHOW DATABASES;")
    console.print("USE sensor_data;")
    console.print("SHOW TABLES;")
    console.print("```")
    
    console.print("\n[yellow]Option 4: Direct S3 query (no setup needed)[/yellow]")
    console.print("```sql")
    console.print("-- Query S3 directly without creating tables")
    console.print("SELECT * FROM json.`s3://expanso-databricks-raw-us-west-2/raw/2025/08/03/*/sensor_data.json`")
    console.print("LIMIT 10;")
    console.print("```")

if __name__ == "__main__":
    console.print("[bold cyan]=== Databricks Connection Diagnostics ===[/bold cyan]\n")
    
    # Run diagnostics
    test_databricks_api()
    check_network()
    suggest_alternatives()
    
    console.print("\n[green]Diagnostics complete![/green]")