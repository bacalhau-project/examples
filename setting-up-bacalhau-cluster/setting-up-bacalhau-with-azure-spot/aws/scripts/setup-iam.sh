#!/usr/bin/env bash
# setup-iam.sh
#
# Script to create required IAM resources for Bacalhau scale testing
set -e

source ./aws-spot-env.sh

function create_role() {
    if aws iam get-role --role-name BacalhauScaleTestRole 2>/dev/null; then
        echo "Role BacalhauScaleTestRole already exists"
    else
        echo "Creating IAM role..."
        aws iam create-role \
            --role-name BacalhauScaleTestRole \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ec2.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }'

        echo "Attaching AmazonSSMManagedInstanceCore policy..."
        aws iam attach-role-policy \
            --role-name BacalhauScaleTestRole \
            --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    fi
}

function create_instance_profile() {
    if aws iam get-instance-profile --instance-profile-name BacalhauScaleTestRole 2>/dev/null; then
        echo "Instance profile BacalhauScaleTestRole already exists"
    else
        echo "Creating instance profile..."
        aws iam create-instance-profile \
            --instance-profile-name BacalhauScaleTestRole

        echo "Adding role to instance profile..."
        aws iam add-role-to-instance-profile \
            --instance-profile-name BacalhauScaleTestRole \
            --role-name BacalhauScaleTestRole
    fi
}

create_role
create_instance_profile

echo "IAM setup complete!" 