#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "click>=8.0.0",
#     "rich>=13.0.0",
# ]
# ///
"""
Clean up old emergency and regional S3 buckets from the pipeline.

This script will:
1. List all S3 buckets matching the pattern
2. Identify emergency and regional buckets
3. Check if they're empty
4. Optionally delete them after confirmation
"""

import boto3
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from typing import List, Dict, Any
import sys

console = Console()

def list_buckets_to_remove(s3_client, prefix: str = "expanso-databricks") -> List[Dict[str, Any]]:
    """List buckets that should be removed (emergency and regional)."""
    buckets_to_remove = []
    
    try:
        response = s3_client.list_buckets()
        
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            
            # Check if it's an emergency or regional bucket
            if prefix in bucket_name and any(x in bucket_name for x in ['emergency', 'regional']):
                # Check if bucket is empty
                try:
                    objects = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    is_empty = 'Contents' not in objects
                    object_count = 0
                    
                    if not is_empty:
                        # Get full count
                        paginator = s3_client.get_paginator('list_objects_v2')
                        page_iterator = paginator.paginate(Bucket=bucket_name)
                        for page in page_iterator:
                            if 'Contents' in page:
                                object_count += len(page['Contents'])
                    
                    buckets_to_remove.append({
                        'name': bucket_name,
                        'created': bucket['CreationDate'],
                        'is_empty': is_empty,
                        'object_count': object_count,
                        'type': 'emergency' if 'emergency' in bucket_name else 'regional'
                    })
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not check bucket {bucket_name}: {e}[/yellow]")
                    
    except Exception as e:
        console.print(f"[red]Error listing buckets: {e}[/red]")
        sys.exit(1)
    
    return buckets_to_remove

def empty_bucket(s3_client, bucket_name: str) -> bool:
    """Empty all objects from a bucket."""
    try:
        # Delete all objects
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name)
        
        delete_count = 0
        for page in page_iterator:
            if 'Contents' in page:
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects:
                    s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects}
                    )
                    delete_count += len(objects)
        
        # Delete all versions (if versioning was enabled)
        try:
            paginator = s3_client.get_paginator('list_object_versions')
            page_iterator = paginator.paginate(Bucket=bucket_name)
            
            for page in page_iterator:
                versions = []
                if 'Versions' in page:
                    versions.extend([{'Key': v['Key'], 'VersionId': v['VersionId']} 
                                   for v in page['Versions']])
                if 'DeleteMarkers' in page:
                    versions.extend([{'Key': d['Key'], 'VersionId': d['VersionId']} 
                                   for d in page['DeleteMarkers']])
                
                if versions:
                    s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': versions}
                    )
                    delete_count += len(versions)
        except:
            pass  # Bucket might not have versioning
        
        if delete_count > 0:
            console.print(f"[green]✓ Deleted {delete_count} objects from {bucket_name}[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error emptying bucket {bucket_name}: {e}[/red]")
        return False

def delete_bucket(s3_client, bucket_name: str) -> bool:
    """Delete an S3 bucket."""
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        console.print(f"[green]✓ Deleted bucket: {bucket_name}[/green]")
        return True
    except Exception as e:
        console.print(f"[red]Error deleting bucket {bucket_name}: {e}[/red]")
        return False

@click.command()
@click.option('--prefix', default='expanso-databricks', help='Bucket name prefix to search')
@click.option('--region', default='us-west-2', help='AWS region')
@click.option('--dry-run', is_flag=True, help='Only show what would be deleted')
@click.option('--force', is_flag=True, help='Skip confirmation prompts')
def main(prefix: str, region: str, dry_run: bool, force: bool):
    """Clean up old emergency and regional S3 buckets."""
    
    console.print("\n[bold blue]🧹 S3 Bucket Cleanup Tool[/bold blue]")
    console.print(f"Searching for emergency and regional buckets with prefix: {prefix}")
    console.print(f"Region: {region}\n")
    
    # Initialize S3 client
    try:
        s3_client = boto3.client('s3', region_name=region)
    except Exception as e:
        console.print(f"[red]Error initializing AWS client: {e}[/red]")
        console.print("[yellow]Make sure you have AWS credentials configured[/yellow]")
        sys.exit(1)
    
    # Find buckets to remove
    buckets_to_remove = list_buckets_to_remove(s3_client, prefix)
    
    if not buckets_to_remove:
        console.print("[green]✓ No emergency or regional buckets found to clean up![/green]")
        return
    
    # Display buckets found
    table = Table(title="Buckets to Remove")
    table.add_column("Bucket Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Created", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Objects", style="red")
    
    for bucket in buckets_to_remove:
        status = "Empty" if bucket['is_empty'] else "Has Data"
        table.add_row(
            bucket['name'],
            bucket['type'].capitalize(),
            bucket['created'].strftime('%Y-%m-%d'),
            status,
            str(bucket['object_count'])
        )
    
    console.print(table)
    
    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print(f"Would delete {len(buckets_to_remove)} bucket(s)")
        return
    
    # Confirm deletion
    if not force:
        if not Confirm.ask(f"\n[bold]Delete {len(buckets_to_remove)} bucket(s)?[/bold]"):
            console.print("[yellow]Cancelled[/yellow]")
            return
    
    # Delete buckets
    console.print("\n[bold]Deleting buckets...[/bold]")
    success_count = 0
    
    for bucket in buckets_to_remove:
        bucket_name = bucket['name']
        
        # Empty bucket if needed
        if not bucket['is_empty']:
            console.print(f"Emptying {bucket_name}...")
            if not empty_bucket(s3_client, bucket_name):
                continue
        
        # Delete bucket
        if delete_bucket(s3_client, bucket_name):
            success_count += 1
    
    # Summary
    console.print(f"\n[bold green]✓ Successfully deleted {success_count}/{len(buckets_to_remove)} buckets[/bold green]")
    
    # Show remaining buckets
    console.print("\n[bold]Remaining pipeline buckets:[/bold]")
    expected_buckets = ['ingestion', 'validated', 'enriched', 'aggregated', 'checkpoints', 'metadata']
    for stage in expected_buckets:
        bucket_name = f"{prefix}-{stage}-{region}"
        console.print(f"  • {bucket_name}")

if __name__ == "__main__":
    main()