#!/usr/bin/env uv
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=3.0.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0",
# ]
# ///

"""Clean up Unity Catalog tables and resolve schema issues."""

import os
import sys
from dotenv import load_dotenv
from databricks import sql
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Load environment variables
load_dotenv()

console = Console()

def cleanup_unity_catalog():
    """Clean up unnecessary tables and fix schema issues."""
    
    # Get Databricks credentials
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    
    # Extract warehouse ID from HTTP_PATH
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
        if "/warehouses/" in http_path:
            warehouse_id = http_path.split("/warehouses/")[-1]
    
    catalog = os.getenv("DATABRICKS_CATALOG", "expanso_databricks_workspace")
    schema = os.getenv("DATABRICKS_DATABASE", "sensor_data")
    
    if not all([host, token, warehouse_id]):
        console.print("[red]❌ Missing Databricks credentials[/red]")
        sys.exit(1)
    
    # Clean up host URL
    host = host.replace("https://", "").replace("http://", "")
    
    console.print(Panel.fit(
        f"🧹 Cleaning Unity Catalog: [cyan]{catalog}.{schema}[/cyan]",
        title="Unity Catalog Cleanup"
    ))
    
    # Tables to DROP (problematic tables with schema issues)
    tables_to_drop = [
        "sensor_data_emergency",    # Has UNRESOLVED_COLUMN error
        "sensor_data_filtered",     # Has UNRESOLVED_COLUMN error
        "sensor_data_raw",          # Has UNRESOLVED_COLUMN error
        "sensor_data_schematized",  # Has UNRESOLVED_COLUMN error
    ]
    
    # Views to DROP (if not needed)
    views_to_drop = [
        "pipeline_monitoring",      # Can recreate if needed
    ]
    
    # Tables to KEEP (working tables with data)
    tables_to_keep = [
        "sensor_data_ingestion",    # 574,803 records - working
        "sensor_data_enriched",     # 17,684 records - working
        "sensor_data_validated",    # 0 records but schema OK
        "sensor_data_aggregated",   # 0 records but schema OK
    ]
    
    try:
        # Connect to Databricks
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                
                # Phase 1: Analyze current state
                console.print("\n[yellow]📊 Phase 1: Analyzing current state...[/yellow]")
                
                cursor.execute(f"SHOW TABLES IN {catalog}.{schema}")
                all_tables = cursor.fetchall()
                
                # Create analysis table
                analysis_table = Table(title="Current Tables Analysis")
                analysis_table.add_column("Table Name", style="cyan")
                analysis_table.add_column("Type", style="magenta")
                analysis_table.add_column("Status", style="green")
                analysis_table.add_column("Action", style="yellow")
                
                for table_info in all_tables:
                    # Debug: print what we get
                    # console.print(f"Debug: table_info = {table_info}")
                    
                    # SHOW TABLES typically returns (catalog, schema, table_name, is_temporary)
                    # Let's handle different formats
                    table_name = None
                    if len(table_info) >= 3:
                        # Standard format: (catalog, schema, table_name, ...)
                        table_name = str(table_info[2])
                    elif len(table_info) >= 2:
                        # Alternate format: (schema, table_name, ...)
                        table_name = str(table_info[1])
                    else:
                        # Fallback
                        table_name = str(table_info[0])
                    
                    # Skip if we couldn't get table name
                    if not table_name:
                        continue
                    
                    # Simple type detection - views usually have "VIEW" in the output somewhere
                    table_type = "TABLE"
                    if "pipeline_monitoring" in table_name or "pipeline_status" in table_name:
                        table_type = "VIEW"
                    
                    # Determine action
                    if table_name in tables_to_drop:
                        action = "🗑️  DROP"
                        status = "❌ Has errors"
                    elif table_name in views_to_drop:
                        action = "🗑️  DROP"
                        status = "📐 View"
                    elif table_name in tables_to_keep:
                        action = "✅ KEEP"
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {catalog}.{schema}.{table_name}")
                            count = cursor.fetchone()[0]
                            status = f"✅ {count:,} records"
                        except:
                            status = "⚠️  Check needed"
                    else:
                        action = "❓ Review"
                        status = "Unknown"
                    
                    analysis_table.add_row(table_name, table_type, status, action)
                
                console.print(analysis_table)
                
                # Phase 2: Drop problematic tables
                console.print("\n[yellow]🗑️  Phase 2: Dropping problematic tables...[/yellow]")
                
                dropped_count = 0
                for table in tables_to_drop:
                    try:
                        # Check if table exists
                        cursor.execute(f"""
                            SELECT COUNT(*) 
                            FROM information_schema.tables 
                            WHERE table_catalog = '{catalog}'
                            AND table_schema = '{schema}'
                            AND table_name = '{table}'
                        """)
                        exists = cursor.fetchone()[0] > 0
                        
                        if exists:
                            console.print(f"  Dropping table: [red]{table}[/red]", end="")
                            cursor.execute(f"DROP TABLE IF EXISTS {catalog}.{schema}.{table}")
                            console.print(" [green]✅ Dropped[/green]")
                            dropped_count += 1
                        else:
                            console.print(f"  Table [cyan]{table}[/cyan] does not exist, skipping")
                    except Exception as e:
                        console.print(f"  [red]⚠️  Could not drop {table}: {str(e)[:100]}[/red]")
                
                # Drop views
                for view in views_to_drop:
                    try:
                        console.print(f"  Dropping view: [yellow]{view}[/yellow]", end="")
                        cursor.execute(f"DROP VIEW IF EXISTS {catalog}.{schema}.{view}")
                        console.print(" [green]✅ Dropped[/green]")
                        dropped_count += 1
                    except Exception as e:
                        console.print(f"  [red]⚠️  Could not drop {view}: {str(e)[:100]}[/red]")
                
                console.print(f"\n[green]Dropped {dropped_count} objects[/green]")
                
                # Phase 3: Verify remaining tables
                console.print("\n[yellow]✅ Phase 3: Verifying remaining tables...[/yellow]")
                
                # Create verification table
                verify_table = Table(title="Remaining Tables")
                verify_table.add_column("Table Name", style="cyan")
                verify_table.add_column("Record Count", justify="right", style="green")
                verify_table.add_column("Status", style="yellow")
                
                cursor.execute(f"SHOW TABLES IN {catalog}.{schema}")
                remaining_tables = cursor.fetchall()
                
                total_records = 0
                for table_info in remaining_tables:
                    # Extract table name safely
                    table_name = None
                    if len(table_info) >= 3:
                        table_name = str(table_info[2])
                    elif len(table_info) >= 2:
                        table_name = str(table_info[1])
                    else:
                        table_name = str(table_info[0])
                    
                    if not table_name:
                        continue
                    if table_name in tables_to_keep:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {catalog}.{schema}.{table_name}")
                            count = cursor.fetchone()[0]
                            total_records += count
                            verify_table.add_row(
                                table_name,
                                f"{count:,}",
                                "✅ Healthy"
                            )
                        except Exception as e:
                            verify_table.add_row(
                                table_name,
                                "N/A",
                                f"⚠️  {str(e)[:30]}"
                            )
                
                console.print(verify_table)
                
                # Phase 4: Create monitoring view for clean tables
                console.print("\n[yellow]📐 Phase 4: Creating monitoring view...[/yellow]")
                
                try:
                    monitoring_sql = f"""
                    CREATE OR REPLACE VIEW {catalog}.{schema}.pipeline_status AS
                    SELECT 
                        'ingestion' as pipeline,
                        COUNT(*) as record_count,
                        MAX(ingested_at) as last_update,
                        MIN(timestamp) as earliest_record,
                        MAX(timestamp) as latest_record
                    FROM {catalog}.{schema}.sensor_data_ingestion
                    UNION ALL
                    SELECT 
                        'enriched' as pipeline,
                        COUNT(*) as record_count,
                        MAX(enriched_at) as last_update,
                        MIN(timestamp) as earliest_record,
                        MAX(timestamp) as latest_record
                    FROM {catalog}.{schema}.sensor_data_enriched
                    UNION ALL
                    SELECT 
                        'validated' as pipeline,
                        COUNT(*) as record_count,
                        MAX(validated_at) as last_update,
                        MIN(timestamp) as earliest_record,
                        MAX(timestamp) as latest_record
                    FROM {catalog}.{schema}.sensor_data_validated
                    UNION ALL
                    SELECT 
                        'aggregated' as pipeline,
                        COUNT(*) as record_count,
                        MAX(aggregated_at) as last_update,
                        MIN(hour) as earliest_record,
                        MAX(hour) as latest_record
                    FROM {catalog}.{schema}.sensor_data_aggregated
                    """
                    
                    cursor.execute(monitoring_sql)
                    console.print("  [green]✅ Created monitoring view: pipeline_status[/green]")
                    
                    # Query the new view
                    cursor.execute(f"SELECT * FROM {catalog}.{schema}.pipeline_status ORDER BY record_count DESC")
                    results = cursor.fetchall()
                    
                    # Display monitoring results
                    monitor_table = Table(title="Pipeline Status")
                    monitor_table.add_column("Pipeline", style="cyan")
                    monitor_table.add_column("Records", justify="right", style="green")
                    monitor_table.add_column("Last Update", style="yellow")
                    
                    for row in results:
                        monitor_table.add_row(
                            row[0],
                            f"{row[1]:,}",
                            str(row[2]) if row[2] else "No data"
                        )
                    
                    console.print(monitor_table)
                    
                except Exception as e:
                    console.print(f"  [red]⚠️  Could not create monitoring view: {e}[/red]")
                
                # Summary
                console.print(Panel.fit(
                    f"""[green]✅ Cleanup Complete![/green]
                    
• Dropped {dropped_count} problematic tables/views
• Kept {len(tables_to_keep)} healthy tables
• Total records preserved: {total_records:,}
• Created monitoring view: pipeline_status

[cyan]Query the monitoring view:[/cyan]
SELECT * FROM {catalog}.{schema}.pipeline_status""",
                    title="Summary"
                ))
                    
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    cleanup_unity_catalog()