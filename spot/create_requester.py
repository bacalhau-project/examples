import boto3
from botocore.exceptions import ClientError
import time

def get_or_create_security_group(ec2, vpc_id):
    group_name = 'BacalhauRequester'
    
    try:
        # Check if the security group already exists
        response = ec2.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': [group_name]},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        if response['SecurityGroups']:
            security_group_id = response['SecurityGroups'][0]['GroupId']
            print(f'Using existing security group {security_group_id} in VPC {vpc_id}.')
            return security_group_id
    except ClientError as e:
        print(f'Error checking for existing security group: {e}')
        return None

    # Create a new security group if it doesn't exist
    try:
        response = ec2.create_security_group(
            GroupName=group_name,
            Description='Security group with port 4222 open',
            VpcId=vpc_id
        )
        security_group_id = response['GroupId']
        print(f'Security Group Created {security_group_id} in VPC {vpc_id}.')

        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 4222,
                    'ToPort': 4222,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 1234,
                    'ToPort': 1234,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print('Ingress Rule Added to Security Group')

        return security_group_id
    except ClientError as e:
        print(f'Error creating security group: {e}')
        return None

def create_ec2_instance(user_data):
    # Create a new EC2 client
    ec2 = boto3.client('ec2', region_name='us-west-2')  # Changed to us-west-2 region

    # Get the default VPC
    vpcs = ec2.describe_vpcs()
    default_vpc = next(vpc for vpc in vpcs['Vpcs'] if vpc['IsDefault'])
    vpc_id = default_vpc['VpcId']
    print(f'Using Default VPC: {vpc_id}')

    # Get a subnet ID from the default VPC
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    subnet_id = subnets['Subnets'][0]['SubnetId']
    print(f'Using Subnet: {subnet_id}')

    # Get or create a security group
    security_group_id = get_or_create_security_group(ec2, vpc_id)
    if not security_group_id:
        print('Failed to get or create security group.')
        return

    # Define the instance parameters
    instance_params = {
        'ImageId': 'ami-03ab9db8dada95e36',  # AMI ID specified
        'InstanceType': 't2.medium',
        'MinCount': 1,
        'MaxCount': 1,
        'UserData': user_data,
        'SecurityGroupIds': [security_group_id],
        'SubnetId': subnet_id,  # Use a subnet from the default VPC
        'TagSpecifications': [
            {
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'BacalhauRequester'}]
            }
        ]
    }

    # Create the instance
    response = ec2.run_instances(**instance_params)

    # Extract the instance ID
    instance_id = response['Instances'][0]['InstanceId']
    print(f'Instance created with ID: {instance_id}')

    return instance_id

def get_instance_public_ip(ec2, instance_id):
    while True:
        try:
            response = ec2.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get('PublicIpAddress')
            if public_ip:
                print(f'Instance Public IP: {public_ip}')
                return public_ip
            else:
                print('Waiting for public IP address...')
                time.sleep(5)
        except ClientError as e:
            print(f'Error fetching instance details: {e}')
            return None

if __name__ == '__main__':
    # Define your user data script (bash script example)
    user_data_script = '''#!/bin/bash
sudo apt-get update && \
sudo apt-get install -y sudo
sudo curl -sSL https://get.bacalhau.org/install.sh | sudo bash

cat <<'EOF' > /start_bacalhau.sh
#!/bin/bash
bacalhau serve --node-type requester
EOF

chmod +x /start_bacalhau.sh

cat <<'EOF' > /etc/systemd/system/bacalhau.service
[Unit]
Description=Bacalhau Daemon
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service

[Service]
Environment="LOG_TYPE=json"
Environment="BACALHAU_PATH=/data"
Environment="BACALHAU_DIR=/data"
Restart=always
RestartSec=5s
ExecStart=bash /start_bacalhau.sh

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable bacalhau
sudo systemctl start bacalhau
'''

    # Create the EC2 instance
    instance_id = create_ec2_instance(user_data_script)
    if instance_id:
        # Create a new EC2 resource
        ec2 = boto3.client('ec2', region_name='us-west-2')  # Make sure to use the same region

        # Get the public IP address of the instance
        get_instance_public_ip(ec2, instance_id)
