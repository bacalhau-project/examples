# Bacalhau Multi-Region AWS Cluster Setup

This Terraform configuration sets up a Bacalhau cluster across multiple AWS regions.

## Prerequisites

- Terraform >= 1.0.0
- AWS CLI configured with appropriate credentials
- SSH key pair for instance access

## Structure 



╷
│ Error: configuring Terraform AWS Provider: no valid credential sources for Terraform AWS Provider found.
│
│ Please see https://registry.terraform.io/providers/hashicorp/aws
│ for more information about providing credentials.
│
│ AWS Error: failed to refresh cached credentials, refresh cached SSO token failed, unable to refresh SSO token, operation error SSO OIDC: CreateToken, https response error StatusCode: 400, RequestID: c0dd4a98-e423-4de2-b972-d749d58afd44, InvalidGrantException:
│
│
│   with provider["registry.terraform.io/hashicorp/aws"].us_east_1,
│   on providers.tf line 3, in provider "aws":
│    3: provider "aws" {
│
╵

Failed to run terraform command: Command '['terraform', 'apply', '-auto-approve', '-var=region=us-west-2', '-var=zone=us-west-2a', '-var=instance_ami=ami-0c0ba4e76e4392ce9', '-var=node_count=3', '-var=instance_type=t3.medium', '-var-file=env.tfvars.json']' returned non-zero exit status 1.