#!/usr/bin/env bash
# aws-spot-env.sh
#
# This file sets environment variables used for launching
# 1,000 AWS Spot Instances with Docker installed.
#
# Usage:
#   source ./aws-spot-env.sh

# AWS CLI & Region
export AWS_REGION="us-west-2"

# Key Pair
export KEY_NAME="BacalhauScaleTestKey"

# Security Group
export SECURITY_GROUP_NAME="bacalhau-scale-test-group"
export SECURITY_GROUP_DESC="Security group for Bacalhau Scale Spot Instances"

# Your public IP for SSH ingress (CIDR /32)
export MY_PUBLIC_IP=$(curl -s ifconfig.me)

# Base AMI to use (Amazon Linux 2 example)
# aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2 --region us-east-1
export BASE_AMI_ID="ami-07d9cf938edb0739b"
export CONFIGURED_AMI_ID="ami-03212e939b49e6f64"

# Instance Type
export INSTANCE_TYPE="t3.micro"

# Number of Spot Instances
export SPOT_INSTANCE_COUNT="100"

# Custom AMI details (if building your own)
export CUSTOM_AMI_NAME="bacalhau-scale-test-ami"
export CUSTOM_AMI_DESCRIPTION="AMI with Docker and Bacalhau preinstalled"

# Tags
export INSTANCE_TAG_KEY="Name"
export INSTANCE_TAG_VALUE="bacalhau-scale-test"

echo "Environment variables for AWS Spot Instances set."
