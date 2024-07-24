import boto3
import time
# Set aws credentials with config file or env variables 

client = boto3.resource('ec2')

#list of ids for all created instances
created_ec2_IDS = []

# create a keypair for created instances
def key_pair():
        keypair = client.create_key_pair(KeyName='botopair')


# create a security group for created instances
def create_sg():
        client = boto3.client('ec2')

        response = client.describe_vpcs()
        vpc_id = response.get("Vpcs", [{}])[0].get("VpcId", "")

        sg = client.create_security_group(
            GroupName="bacalhau_sg",
            Description="Security group with port 4222 open",
            VpcId=vpc_id,
        )

        security_group_id = sg["GroupId"]
        print(f"Security Group Created {security_group_id} in VPC {vpc_id}.")

        data = client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 4222,
                    "ToPort": 4222,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1234,
                    "ToPort": 1234,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
            ],
        )
        print("Ingress Rule Added to Security Group")

# create requester instance and get ip
def create_requester():
        requester_script='''#!/bin/bash
        sudo apt-get update
        sudo apt-get install -y docker.io
        sudo systemctl start docker
        sudo systemctl enable docker
        curl -sL https://get.bacalhau.org/install.sh | bash
        sudo bacalhau config auto-resources
        sudo bacalhau serve --node-type=requester --requester-job-translation-enabled --job-selection-accept-networked    
'''
        # instance creation
        instances = client.create_instances(
                ImageId="ami-04a81a99f5ec58529",
                KeyName="botopair",
                SecurityGroups=[
                        'bacalhau_sg',
                ],
                MinCount=1,
                MaxCount=1,
                InstanceType="t2.micro",
                UserData=requester_script,
                TagSpecifications=[
                        {
                                'ResourceType':'instance',
                                'Tags':[
                                        {
                                                'Key':'Bacalhau',
                                                'Value':'Testinstance'
                                        },
                                        {
                                                'Key':'BacalhauRequester',
                                                'Value':'Headinstance'
                                        },
                                ]
                        },
                ],
            )
        
        created_ec2_IDS.append(f"{instances[0].id}")
        
        # create waiter to ensure the requester is created before compute nodes
        client2 = boto3.client('ec2')
        instance_ids = []
        instance_ids.append(f"{instances[0].id}")
        waiter = client2.get_waiter('instance_status_ok').wait(InstanceIds=instance_ids)

        #collect requester ip address
        response = client2.describe_instances(InstanceIds=[f"{instances[0].id}"])
        requester_ip = response['Reservations'][0]['Instances'][0]['PublicIpAddress']
        return requester_ip

# create data generating compute nodes
def create_compute_nodes(requesterip):
        print(f"your Requester Node Ip Address is {requesterip}")
        compute_script=f'''#!/bin/bash
        sudo apt-get update
        sudo apt-get install python3-pip -y
        sudo pip install faker-cli -I --break-system-packages
        sudo fake -t cloudfront -n 100 -f csv > /home/ubuntu/data.csv
        sudo apt-get install -y docker.io
        sudo systemctl start docker
        sudo systemctl enable docker
        curl -sL https://get.bacalhau.org/install.sh | bash
        sudo bacalhau config auto-resources
        sudo bacalhau serve --node-type=compute --orchestrators=nats://{requesterip}:4222 --job-selection-accept-networked 

'''
        instances = client.create_instances(
                ImageId="ami-04a81a99f5ec58529",
                KeyName="botopair",
                SecurityGroups=[
                        'bacalhau_sg',
                ],
                MinCount=3,
                MaxCount=3,
                InstanceType="t2.medium",
                UserData=compute_script,
                TagSpecifications=[
                        {
                                'ResourceType':'instance',
                                'Tags':[
                                        {
                                                'Key':'Bacalhau',
                                                'Value':'Testinstance'
                                        },
                                ]
                        },
                ],
            )        
        
        for instance in instances:
                created_ec2_IDS.append(instance.id)
                

if __name__ == '__main__':
        key_pair()
        create_sg()
        reques=create_requester()
        time.sleep(20)
        create_compute_nodes(reques)
        print(f"Instance IDs for all created EC2s {created_ec2_IDS}")