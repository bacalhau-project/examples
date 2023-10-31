# Bacalhau Log Vending AWS CDK Stack

## Overview

Welcome to Bacalhau AWS CDK Stack for Log Vending! This project provisions a stack for Bacalhau, a distributed compute orchestration framework, using AWS Cloud Development Kit (CDK).

This stack sets up:
- VPC with public and private subnets
- EC2 instances for the orchestrator and compute nodes
- An OpenSearch domain
- An S3 bucket for raw access logs
- IAM roles and security groups

## Requirements
- Node.js v14.x.x or later
- AWS CDK CLI
- AWS CLI

## Getting Started

### Clone the Repository
```
git clone https://github.com/bacalhau-project/examples.git
cd log-vending/cdk 
```

### Install Dependencies
```
npm install
```

### Bootstrap AWS CDK
This step is required if you haven't used AWS CDK on your AWS account.
```
cdk bootstrap
```


### Deploy the Stack

Deploying the stack is as simple as running the following command:

```bash
cdk deploy
```

All of the context configurations are optional. If you'd like to customize your deployment, you can add them like so:

```bash
cdk deploy --context bacalhauVersion=<version> \
            --context targetPlatform=<platform> \
            --context orchestratorInstanceType=<EC2 instance type> \
            --context webServerInstanceType=<EC2 instance type> \
            --context webServerInstanceCount=<number of compute nodes> \
            --context keyName=<SSH key pair name>
```

Feel free to replace the placeholders with your specific values, but remember, these are all optional enhancements to tailor the stack to your needs. Though you need to specify `keyName` if you want to SSH into the instances.


## Architecture

- **VPC**: Custom VPC (`10.1.0.0/16`) with 3 availability zones.
- **EC2 Instances**: Using Ubuntu 20.04. Security groups permit SSH and Bacalhau API access.
- **OpenSearch**: `t3.small.search` instance type with a master user.
- **S3 Bucket**: Used for storing raw logs.

## Outputs

- **Orchestrator Public IP**: The public IP address of the Orchestrator instance.
- **OpenSearch Endpoint**: The endpoint for accessing OpenSearch.
- **OpenSearch Dashboard**: The URL for OpenSearch Dashboards.
- **Bucket Name**: The name of the S3 bucket.

To get the OpenSearch master password, run:
```
aws secretsmanager get-secret-value --secret-id "<Secret ARN>" --query 'SecretString' --output text
```

## Cleaning Up

To delete the deployed stack:
```
cdk destroy
```