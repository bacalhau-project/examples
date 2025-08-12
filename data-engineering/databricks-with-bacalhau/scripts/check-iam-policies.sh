#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "rich>=13.0.0",
#     "click>=8.0.0",
# ]
# ///
"""
Check IAM policies for references to old emergency and regional buckets.

This script will:
1. Find IAM roles used by Databricks
2. Check their policies for old bucket references
3. Provide updated policy JSON if needed
"""

import boto3
import click
import json
from rich.console import Console
from rich.syntax import Syntax
from typing import List, Dict, Any
import sys

console = Console()

def find_databricks_roles(iam_client) -> List[str]:
    """Find IAM roles that appear to be for Databricks."""
    databricks_roles = []
    
    try:
        paginator = iam_client.get_paginator('list_roles')
        for page in paginator.paginate():
            for role in page['Roles']:
                role_name = role['RoleName']
                # Look for roles with databricks, expanso, or unity-catalog in the name
                if any(x in role_name.lower() for x in ['databricks', 'expanso', 'unity-catalog']):
                    databricks_roles.append(role_name)
    except Exception as e:
        console.print(f"[red]Error listing IAM roles: {e}[/red]")
    
    return databricks_roles

def check_policy_for_old_buckets(policy_document: dict) -> List[str]:
    """Check if a policy document references old buckets."""
    old_bucket_references = []
    
    def check_resource(resource):
        if isinstance(resource, str):
            if any(x in resource for x in ['emergency', 'regional']):
                old_bucket_references.append(resource)
        elif isinstance(resource, list):
            for r in resource:
                check_resource(r)
    
    if 'Statement' in policy_document:
        for statement in policy_document['Statement']:
            if 'Resource' in statement:
                check_resource(statement['Resource'])
    
    return old_bucket_references

def get_updated_policy(policy_document: dict, prefix: str, region: str) -> dict:
    """Get an updated policy with correct bucket references."""
    updated_policy = json.loads(json.dumps(policy_document))  # Deep copy
    
    # Define the correct buckets
    correct_buckets = [
        f"arn:aws:s3:::{prefix}-databricks-ingestion-{region}",
        f"arn:aws:s3:::{prefix}-databricks-validated-{region}",
        f"arn:aws:s3:::{prefix}-databricks-enriched-{region}",
        f"arn:aws:s3:::{prefix}-databricks-aggregated-{region}",
        f"arn:aws:s3:::{prefix}-databricks-checkpoints-{region}",
        f"arn:aws:s3:::{prefix}-databricks-metadata-{region}"
    ]
    
    def update_resource(resource):
        if isinstance(resource, str):
            # Remove emergency and regional bucket references
            if 'emergency' in resource or 'regional' in resource:
                return None
            return resource
        elif isinstance(resource, list):
            updated = []
            for r in resource:
                updated_r = update_resource(r)
                if updated_r:
                    updated.append(updated_r)
            return updated
        return resource
    
    if 'Statement' in updated_policy:
        for statement in updated_policy['Statement']:
            if 'Resource' in statement:
                # Update resources
                original_resources = statement['Resource']
                updated_resources = update_resource(original_resources)
                
                # If we removed all resources, add the correct ones
                if not updated_resources or (isinstance(updated_resources, list) and len(updated_resources) == 0):
                    # Add correct bucket ARNs
                    statement['Resource'] = correct_buckets + [b + "/*" for b in correct_buckets]
                else:
                    statement['Resource'] = updated_resources
    
    return updated_policy

@click.command()
@click.option('--prefix', default='expanso', help='Bucket name prefix')
@click.option('--region', default='us-west-2', help='AWS region')
@click.option('--role-name', help='Specific role name to check')
@click.option('--fix', is_flag=True, help='Show updated policy JSON')
def main(prefix: str, region: str, role_name: str, fix: bool):
    """Check IAM policies for old bucket references."""
    
    console.print("\n[bold blue]🔍 IAM Policy Checker[/bold blue]")
    console.print("Checking for emergency and regional bucket references in IAM policies...\n")
    
    # Initialize IAM client
    try:
        iam_client = boto3.client('iam')
    except Exception as e:
        console.print(f"[red]Error initializing AWS IAM client: {e}[/red]")
        console.print("[yellow]Make sure you have AWS credentials configured[/yellow]")
        sys.exit(1)
    
    # Find roles to check
    if role_name:
        roles_to_check = [role_name]
    else:
        console.print("Finding Databricks-related IAM roles...")
        roles_to_check = find_databricks_roles(iam_client)
    
    if not roles_to_check:
        console.print("[yellow]No Databricks-related IAM roles found[/yellow]")
        console.print("You can specify a role with --role-name")
        return
    
    console.print(f"Found {len(roles_to_check)} role(s) to check\n")
    
    roles_with_issues = []
    
    for role in roles_to_check:
        console.print(f"Checking role: [cyan]{role}[/cyan]")
        
        try:
            # Get inline policies
            inline_policies = iam_client.list_role_policies(RoleName=role)
            for policy_name in inline_policies.get('PolicyNames', []):
                policy = iam_client.get_role_policy(RoleName=role, PolicyName=policy_name)
                policy_doc = policy['PolicyDocument']
                
                old_refs = check_policy_for_old_buckets(policy_doc)
                if old_refs:
                    console.print(f"  [red]✗ Found old bucket references in inline policy '{policy_name}':[/red]")
                    for ref in old_refs:
                        console.print(f"    - {ref}")
                    roles_with_issues.append({
                        'role': role,
                        'policy_name': policy_name,
                        'policy_type': 'inline',
                        'policy_document': policy_doc,
                        'old_references': old_refs
                    })
            
            # Get attached policies
            attached_policies = iam_client.list_attached_role_policies(RoleName=role)
            for policy in attached_policies.get('AttachedPolicies', []):
                policy_arn = policy['PolicyArn']
                policy_name = policy['PolicyName']
                
                # Get the default version
                policy_details = iam_client.get_policy(PolicyArn=policy_arn)
                version_id = policy_details['Policy']['DefaultVersionId']
                
                # Get the policy document
                policy_version = iam_client.get_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=version_id
                )
                policy_doc = policy_version['PolicyVersion']['Document']
                
                old_refs = check_policy_for_old_buckets(policy_doc)
                if old_refs:
                    console.print(f"  [red]✗ Found old bucket references in attached policy '{policy_name}':[/red]")
                    for ref in old_refs:
                        console.print(f"    - {ref}")
                    roles_with_issues.append({
                        'role': role,
                        'policy_name': policy_name,
                        'policy_type': 'attached',
                        'policy_arn': policy_arn,
                        'policy_document': policy_doc,
                        'old_references': old_refs
                    })
            
            if role not in [r['role'] for r in roles_with_issues]:
                console.print(f"  [green]✓ No old bucket references found[/green]")
                
        except Exception as e:
            console.print(f"  [yellow]Warning: Could not check role: {e}[/yellow]")
    
    if not roles_with_issues:
        console.print("\n[green]✓ No IAM policies found with old bucket references![/green]")
        return
    
    # Show fixes if requested
    if fix:
        console.print("\n[bold]Updated Policies:[/bold]\n")
        
        for issue in roles_with_issues:
            console.print(f"[bold cyan]Role: {issue['role']}[/bold cyan]")
            console.print(f"Policy: {issue['policy_name']} ({issue['policy_type']})")
            console.print("\nUpdated policy document:")
            
            updated_policy = get_updated_policy(issue['policy_document'], prefix, region)
            
            syntax = Syntax(
                json.dumps(updated_policy, indent=2),
                "json",
                theme="monokai",
                line_numbers=True
            )
            console.print(syntax)
            
            console.print("\n[yellow]To update this policy:[/yellow]")
            if issue['policy_type'] == 'inline':
                console.print(f"aws iam put-role-policy --role-name {issue['role']} \\")
                console.print(f"  --policy-name {issue['policy_name']} \\")
                console.print(f"  --policy-document file://updated-policy.json")
            else:
                console.print(f"1. Create a new version of the policy:")
                console.print(f"   aws iam create-policy-version --policy-arn {issue['policy_arn']} \\")
                console.print(f"     --policy-document file://updated-policy.json --set-as-default")
            
            console.print("\n" + "="*60 + "\n")
    
    else:
        console.print(f"\n[yellow]Found {len(roles_with_issues)} role(s) with old bucket references[/yellow]")
        console.print("Run with --fix to see updated policy documents")

if __name__ == "__main__":
    main()