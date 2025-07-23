#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "click",
#     "rich",
# ]
# ///

"""
Set up S3 infrastructure for Databricks data pipeline.

This script:
1. Creates S3 buckets for different data processing scenarios
2. Creates an IAM service account with appropriate permissions
3. Downloads and stores credentials locally for node access
4. Sets up lifecycle policies for automatic file deletion
"""

import sys
import os
import boto3
import click
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional, Tuple

console = Console()

BUCKET_SCENARIOS = {
    "raw": "Raw unprocessed sensor data",
    "schematized": "Data with enforced schemas and validation",
    "filtered": "Filtered data based on business rules",
    "emergency": "High-priority anomaly or alert data"
}

# Lifecycle policies for each bucket type (in days)
LIFECYCLE_POLICIES = {
    "raw": {
        "transition_to_ia": 30,      # Move to Infrequent Access after 30 days
        "transition_to_glacier": 90,   # Move to Glacier after 90 days
        "expiration": 365             # Delete after 1 year
    },
    "schematized": {
        "transition_to_ia": 60,
        "expiration": 730             # Delete after 2 years
    },
    "filtered": {
        "transition_to_ia": 90,
        "expiration": 1095            # Delete after 3 years
    },
    "emergency": {
        "expiration": 2555            # Keep for 7 years (compliance)
    }
}

def get_bucket_name(prefix: str, scenario: str, region: str) -> str:
    """Generate bucket name following AWS naming conventions."""
    return f"{prefix}-databricks-{scenario}-{region}".lower()

def create_lifecycle_policy(scenario: str) -> Dict:
    """Create lifecycle configuration based on scenario."""
    policy = LIFECYCLE_POLICIES.get(scenario, {})
    rules = []
    
    rule = {
        'ID': f'Lifecycle policy for {scenario} data',
        'Status': 'Enabled',
        'Filter': {'Prefix': ''}
    }
    
    # Add transitions
    transitions = []
    if 'transition_to_ia' in policy:
        transitions.append({
            'Days': policy['transition_to_ia'],
            'StorageClass': 'STANDARD_IA'
        })
    if 'transition_to_glacier' in policy:
        transitions.append({
            'Days': policy['transition_to_glacier'],
            'StorageClass': 'GLACIER'
        })
    
    if transitions:
        rule['Transitions'] = transitions
    
    # Add expiration
    if 'expiration' in policy:
        rule['Expiration'] = {'Days': policy['expiration']}
    
    rules.append(rule)
    return {'Rules': rules}

def create_bucket_with_lifecycle(s3_client, bucket_name: str, region: str, scenario: str) -> bool:
    """Create an S3 bucket with lifecycle policies."""
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
        
        # Enable server-side encryption
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
        
        # Add lifecycle policy
        lifecycle_config = create_lifecycle_policy(scenario)
        if lifecycle_config['Rules']:
            s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            console.print(f"  [dim]Added lifecycle policy: {json.dumps(LIFECYCLE_POLICIES.get(scenario, {}), indent=2)}[/dim]")
        
        # Add tags
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'Project', 'Value': 'databricks-pipeline'},
                    {'Key': 'Environment', 'Value': 'production'},
                    {'Key': 'DataType', 'Value': scenario},
                    {'Key': 'ManagedBy', 'Value': 'setup-s3-infrastructure'}
                ]
            }
        )
        
        console.print(f"[green]✓[/green] Created bucket: {bucket_name}")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            console.print(f"[yellow]![/yellow] Bucket already exists: {bucket_name}")
            return True
        elif e.response['Error']['Code'] == 'BucketAlreadyExists':
            console.print(f"[red]✗[/red] Bucket name already taken: {bucket_name}")
            return False
        else:
            console.print(f"[red]✗[/red] Error creating bucket {bucket_name}: {e}")
            return False

def create_iam_user_and_policy(iam_client, prefix: str, bucket_names: List[str]) -> Optional[Tuple[str, str]]:
    """Create IAM user with policy for S3 access."""
    user_name = f"{prefix}-databricks-s3-user"
    policy_name = f"{prefix}-databricks-s3-policy"
    
    try:
        # Create IAM user
        try:
            iam_client.create_user(UserName=user_name)
            console.print(f"[green]✓[/green] Created IAM user: {user_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                console.print(f"[yellow]![/yellow] IAM user already exists: {user_name}")
            else:
                raise
        
        # Create policy document
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ListBuckets",
                    "Effect": "Allow",
                    "Action": [
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                        "s3:GetBucketVersioning"
                    ],
                    "Resource": [f"arn:aws:s3:::{bucket}" for bucket in bucket_names]
                },
                {
                    "Sid": "ReadWriteObjects",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:DeleteObjectVersion"
                    ],
                    "Resource": [f"arn:aws:s3:::{bucket}/*" for bucket in bucket_names]
                }
            ]
        }
        
        # Attach inline policy to user
        iam_client.put_user_policy(
            UserName=user_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        console.print(f"[green]✓[/green] Attached S3 access policy to user")
        
        # Create access key
        response = iam_client.create_access_key(UserName=user_name)
        access_key = response['AccessKey']['AccessKeyId']
        secret_key = response['AccessKey']['SecretAccessKey']
        
        console.print(f"[green]✓[/green] Created access keys for user")
        
        return access_key, secret_key
        
    except ClientError as e:
        console.print(f"[red]✗[/red] Error creating IAM user: {e}")
        return None

def save_credentials(prefix: str, region: str, access_key: str, secret_key: str, 
                    bucket_names: Dict[str, str], output_dir: str) -> None:
    """Save credentials and configuration to local files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save AWS credentials format
    creds_file = output_path / f"{prefix}-s3-credentials"
    with open(creds_file, 'w') as f:
        f.write(f"[{prefix}-databricks]\n")
        f.write(f"aws_access_key_id = {access_key}\n")
        f.write(f"aws_secret_access_key = {secret_key}\n")
        f.write(f"region = {region}\n")
    
    console.print(f"[green]✓[/green] Saved AWS credentials to: {creds_file}")
    
    # Save environment variables format
    env_file = output_path / f"{prefix}-s3-env.sh"
    with open(env_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write(f"# S3 credentials for {prefix} Databricks pipeline\n")
        f.write(f"# Generated on {datetime.now().isoformat()}\n\n")
        f.write(f"export AWS_ACCESS_KEY_ID='{access_key}'\n")
        f.write(f"export AWS_SECRET_ACCESS_KEY='{secret_key}'\n")
        f.write(f"export AWS_DEFAULT_REGION='{region}'\n")
        f.write(f"export S3_BUCKET_PREFIX='{prefix}'\n")
        f.write(f"export S3_REGION='{region}'\n")
        for scenario, bucket in bucket_names.items():
            f.write(f"export S3_BUCKET_{scenario.upper()}='{bucket}'\n")
    
    os.chmod(env_file, 0o600)  # Make it readable only by owner
    console.print(f"[green]✓[/green] Saved environment variables to: {env_file}")
    
    # Save JSON configuration
    config_file = output_path / f"{prefix}-s3-config.json"
    config = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "region": region,
        "s3_configuration": {
            "prefix": prefix,
            "region": region,
            "buckets": bucket_names
        },
        "created_at": datetime.now().isoformat()
    }
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    os.chmod(config_file, 0o600)
    console.print(f"[green]✓[/green] Saved JSON configuration to: {config_file}")
    
    # Save YAML configuration for uploader
    yaml_file = output_path / f"{prefix}-databricks-s3.yaml"
    with open(yaml_file, 'w') as f:
        f.write(f"# S3 configuration for {prefix} Databricks pipeline\n")
        f.write(f"# Generated on {datetime.now().isoformat()}\n\n")
        f.write("s3_buckets:\n")
        for scenario, bucket in bucket_names.items():
            f.write(f"  {scenario}: {bucket}\n")
        f.write(f"\ns3_region: {region}\n")
        f.write(f"s3_prefix: {prefix}\n")
    
    console.print(f"[green]✓[/green] Saved YAML configuration to: {yaml_file}")

@click.command()
@click.option('--prefix', '-p', help='Prefix for bucket names (e.g., your-company)')
@click.option('--region', '-r', default='us-east-1', help='AWS region for buckets')
@click.option('--output-dir', '-o', default='./credentials', help='Directory to save credentials')
@click.option('--skip-iam', is_flag=True, help='Skip IAM user creation (only create buckets)')
@click.option('--test-creds', is_flag=True, help='Test AWS credentials and exit')
@click.option('--profile', help='AWS profile to use (e.g., from aws configure list-profiles)')
def main(prefix: str, region: str, output_dir: str, skip_iam: bool, test_creds: bool, profile: Optional[str]):
    """Set up complete S3 infrastructure for Databricks data pipeline."""
    
    # Show which credentials we're using
    if profile:
        console.print(f"[dim]Using AWS profile: {profile}[/dim]")
    else:
        console.print("[dim]Testing AWS credentials...[/dim]")
    
    try:
        # Create session with optional profile
        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            session = boto3.Session()
        sts_client = session.client('sts')
        
        # Test credentials with a simple API call
        account_info = sts_client.get_caller_identity()
        account_id = account_info['Account']
        user_arn = account_info['Arn']
        
        # Clear the testing message
        console.print("\033[1A\033[K", end="")  # Move up one line and clear
        
        if test_creds:
            # Just show credential info and exit
            console.print(Panel.fit(
                f"[green]✓ AWS credentials are valid![/green]\n\n"
                f"[bold]Account ID:[/bold] {account_id}\n"
                f"[bold]User/Role:[/bold] {user_arn}\n"
                f"[bold]Region:[/bold] {region}",
                title="AWS Credential Test"
            ))
            return
        
        # Check if prefix is provided for actual bucket creation
        if not prefix:
            console.print("[red]Error: --prefix is required when creating buckets[/red]")
            console.print("\nUsage:")
            console.print("  Test credentials: [cyan]uv run scripts/setup-s3-infrastructure.py --test-creds[/cyan]")
            console.print("  Create buckets: [cyan]uv run scripts/setup-s3-infrastructure.py -p your-prefix[/cyan]")
            sys.exit(1)
        
        # Now show the main panel since credentials are valid
        console.print(Panel.fit(
            "[bold]S3 Infrastructure Setup for Databricks Pipeline[/bold]\n"
            "This will create:\n"
            "• 4 S3 buckets with lifecycle policies\n"
            "• IAM service account with access permissions\n"
            "• Local credential files for node deployment",
            title="Setup Overview"
        ))
        
        console.print(f"\n[bold]AWS Account:[/bold] {account_id}")
        console.print(f"[bold]User/Role:[/bold] {user_arn}")
        console.print(f"[bold]Region:[/bold] {region}\n")
        
        # Initialize remaining AWS clients
        s3_client = session.client('s3', region_name=region)
        iam_client = session.client('iam')
        
    except NoCredentialsError:
        console.print("[red]Error: AWS credentials not found.[/red]")
        console.print("\nPlease configure AWS credentials using one of these methods:")
        console.print("  1. AWS SSO: [cyan]aws sso login[/cyan]")
        console.print("  2. AWS Configure: [cyan]aws configure[/cyan]")
        console.print("  3. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        console.print("  4. IAM role (if on EC2)")
        console.print("\n[yellow]Tip: If using AWS SSO, run:[/yellow]")
        console.print("  [dim]aws sso login --profile your-profile-name[/dim]")
        sys.exit(1)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidClientTokenId':
            console.print("[red]Error: Invalid AWS credentials or expired SSO session.[/red]")
            console.print("\nPossible causes:")
            console.print("1. [yellow]Environment variables overriding SSO[/yellow] - Check with: [cyan]env | grep AWS_[/cyan]")
            console.print("   Fix: [cyan]unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY[/cyan]")
            console.print("\n2. [yellow]SSO session expired[/yellow]")
            console.print("   Fix: [cyan]aws sso login[/cyan]")
            console.print("\n3. [yellow]Using wrong profile[/yellow]")
            console.print("   Fix: Use [cyan]--profile[/cyan] flag with one of:")
            # Try to list profiles
            try:
                import subprocess
                result = subprocess.run(['aws', 'configure', 'list-profiles'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    profiles = result.stdout.strip().split('\n')
                    for p in profiles[:5]:  # Show first 5 profiles
                        console.print(f"        [dim]--profile {p}[/dim]")
                    if len(profiles) > 5:
                        console.print(f"        [dim](and {len(profiles) - 5} more...)[/dim]")
            except:
                pass
        elif error_code == 'ExpiredToken':
            console.print("[red]Error: AWS security token has expired.[/red]")
            console.print("\nPlease refresh your AWS SSO session:")
            console.print("  [cyan]aws sso login[/cyan]")
        else:
            console.print(f"[red]AWS Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error initializing AWS client: {e}[/red]")
        console.print("\n[yellow]Debug info:[/yellow]")
        console.print(f"  Error type: {type(e).__name__}")
        console.print(f"  Error details: {str(e)}")
        sys.exit(1)
    
    # Create buckets
    console.print("[bold]Creating S3 Buckets[/bold]\n")
    created_buckets = {}
    
    for scenario, description in BUCKET_SCENARIOS.items():
        bucket_name = get_bucket_name(prefix, scenario, region)
        console.print(f"\n[cyan]Creating {scenario} bucket:[/cyan] {bucket_name}")
        console.print(f"  Description: {description}")
        
        success = create_bucket_with_lifecycle(s3_client, bucket_name, region, scenario)
        if success:
            created_buckets[scenario] = bucket_name
    
    # Display results
    table = Table(title="\nS3 Bucket Summary")
    table.add_column("Scenario", style="cyan")
    table.add_column("Bucket Name", style="green")
    table.add_column("Lifecycle Policy", style="yellow")
    
    for scenario, bucket_name in created_buckets.items():
        policy = LIFECYCLE_POLICIES.get(scenario, {})
        policy_summary = []
        if 'transition_to_ia' in policy:
            policy_summary.append(f"IA: {policy['transition_to_ia']}d")
        if 'transition_to_glacier' in policy:
            policy_summary.append(f"Glacier: {policy['transition_to_glacier']}d")
        if 'expiration' in policy:
            policy_summary.append(f"Delete: {policy['expiration']}d")
        
        table.add_row(
            scenario.capitalize(),
            bucket_name,
            ", ".join(policy_summary) if policy_summary else "None"
        )
    
    console.print(table)
    
    # Create IAM user and save credentials
    if not skip_iam and created_buckets:
        console.print(f"\n[bold]Creating IAM Service Account[/bold]\n")
        
        credentials = create_iam_user_and_policy(
            iam_client, 
            prefix, 
            list(created_buckets.values())
        )
        
        if credentials:
            access_key, secret_key = credentials
            
            # Save all credentials and configurations
            console.print(f"\n[bold]Saving Credentials[/bold]\n")
            save_credentials(
                prefix, region, access_key, secret_key,
                created_buckets, output_dir
            )
            
            # Display usage instructions
            console.print(Panel(
                f"[bold green]Setup Complete![/bold green]\n\n"
                f"To use these credentials on a node:\n\n"
                f"1. Copy credential files from [cyan]{output_dir}[/cyan] to the node\n"
                f"2. Source the environment variables:\n"
                f"   [dim]source {output_dir}/{prefix}-s3-env.sh[/dim]\n\n"
                f"3. Or use the AWS credentials file:\n"
                f"   [dim]export AWS_SHARED_CREDENTIALS_FILE={output_dir}/{prefix}-s3-credentials[/dim]\n"
                f"   [dim]export AWS_PROFILE={prefix}-databricks[/dim]\n\n"
                f"The credentials provide read/write access to all created buckets.",
                title="Next Steps"
            ))
        else:
            console.print("[red]Failed to create IAM credentials[/red]")
    
    elif skip_iam:
        console.print("\n[yellow]Skipped IAM user creation (--skip-iam flag)[/yellow]")
        console.print("You'll need to configure S3 access credentials separately.")

if __name__ == "__main__":
    main()