#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "click>=8.0.0",
# ]
# ///
"""
Create S3 buckets with proper pipeline stage names for Databricks with Bacalhau demo.
"""

import boto3
import click
import json
from datetime import datetime
from typing import List, Dict, Any

# Pipeline stage bucket mapping
PIPELINE_BUCKETS = {
    "ingestion": "Raw sensor data as ingested from edge devices",
    "validated": "Schema-validated data with quality checks",
    "enriched": "Data enriched with Bacalhau metadata and privacy protection",
    "aggregated": "Time-window aggregated data with anomaly detection",
    "checkpoints": "Auto Loader checkpoint storage",
    "metadata": "Pipeline and node metadata storage"
}

def create_bucket_with_config(s3_client, bucket_name: str, region: str, description: str):
    """Create S3 bucket with proper configuration"""
    try:
        # Create bucket
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        
        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # Enable encryption
        s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }]
            }
        )
        
        # Add tags
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'Project', 'Value': 'databricks-bacalhau-demo'},
                    {'Key': 'Environment', 'Value': 'demo'},
                    {'Key': 'Description', 'Value': description},
                    {'Key': 'CreatedBy', 'Value': 'pipeline-setup-script'},
                    {'Key': 'CreatedAt', 'Value': datetime.now().isoformat()}
                ]
            }
        )
        
        # Set lifecycle policy for ingestion bucket (move to cheaper storage)
        if 'ingestion' in bucket_name:
            lifecycle_config = {
                'Rules': [{
                    'ID': 'MoveToIA',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': ''},  # Apply to all objects
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'
                        },
                        {
                            'Days': 90,
                            'StorageClass': 'GLACIER'
                        }
                    ]
                }]
            }
            try:
                s3_client.put_bucket_lifecycle_configuration(
                    Bucket=bucket_name,
                    LifecycleConfiguration=lifecycle_config
                )
                print(f"  → Added lifecycle policy to {bucket_name}")
            except Exception as e:
                print(f"  ⚠️  Could not add lifecycle policy: {e}")
        
        print(f"✓ Created bucket: {bucket_name}")
        return True
        
    except s3_client.exceptions.BucketAlreadyExists:
        print(f"⚠️  Bucket already exists: {bucket_name}")
        return False
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"✓ Bucket already owned by you: {bucket_name}")
        return True
    except Exception as e:
        print(f"✗ Error creating bucket {bucket_name}: {e}")
        return False

def create_initial_structure(s3_client, bucket_name: str, stage: str):
    """Create initial folder structure in bucket"""
    # Create .keep file to establish folder structure
    keep_content = f"Pipeline stage: {stage}\nCreated: {datetime.now().isoformat()}\n"
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f"{stage}/.keep",
            Body=keep_content.encode('utf-8')
        )
        print(f"  → Created initial structure in {bucket_name}")
    except Exception as e:
        print(f"  ⚠️  Could not create initial structure: {e}")

@click.command()
@click.option('--prefix', default='expanso', help='Bucket name prefix')
@click.option('--region', default='us-west-2', help='AWS region')
@click.option('--create-folders', is_flag=True, help='Create initial folder structure')
def main(prefix: str, region: str, create_folders: bool):
    """Create S3 buckets for Databricks with Bacalhau pipeline demo"""
    
    print(f"\n🚀 Creating S3 buckets for pipeline demo")
    print(f"   Prefix: {prefix}")
    print(f"   Region: {region}")
    print(f"   Buckets to create: {len(PIPELINE_BUCKETS)}")
    print()
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=region)
    
    created_buckets = []
    
    # Create each bucket
    for stage, description in PIPELINE_BUCKETS.items():
        bucket_name = f"{prefix}-databricks-{stage}-{region}"
        
        if create_bucket_with_config(s3_client, bucket_name, region, description):
            created_buckets.append(bucket_name)
            
            if create_folders and stage not in ['checkpoints', 'metadata']:
                create_initial_structure(s3_client, bucket_name, stage)
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Total buckets: {len(PIPELINE_BUCKETS)}")
    print(f"   Created: {len(created_buckets)}")
    print(f"   Existing: {len(PIPELINE_BUCKETS) - len(created_buckets)}")
    
    # Generate configuration snippet
    if created_buckets:
        print(f"\n📝 Configuration snippet for your YAML files:")
        print("```yaml")
        print("s3:")
        print("  buckets:")
        for stage in PIPELINE_BUCKETS.keys():
            bucket_name = f"{prefix}-databricks-{stage}-{region}"
            print(f"    {stage}: {bucket_name}")
        print("```")
        
        print(f"\n📝 Databricks notebook configuration:")
        print("```python")
        print("buckets = {")
        for stage in ['ingestion', 'validated', 'enriched', 'aggregated']:
            bucket_name = f"{prefix}-databricks-{stage}-{region}"
            print(f'    "{stage}": "s3://{bucket_name}/{stage}/",')
        print("}")
        print("```")

if __name__ == "__main__":
    main()