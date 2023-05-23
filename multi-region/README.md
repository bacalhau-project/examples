# Multi-Region Bacalhau Nodes with Tailscale

## Overview


Create a tailscale account.
Add a tag to your tailscale account - https://login.tailscale.com/admin/acls

```jsonc
// Example/default ACLs for unrestricted connections.
{
	// Declare static groups of users. Use autogroups for all users or users with a specific role.
	// "groups": {
	//  	"group:example": ["alice@example.com", "bob@example.com"],
	// },

	// Define the tags which can be applied to devices and by which users.
	"tagOwners": {
    "tag:bacalhau-multi-region-example": ["autogroup:admin"],
	},

	// Define access control lists for users, groups, autogroups, tags,
	// Tailscale IP addresses, and subnet ranges.
	"acls": [
		// Allow all connections.
		// Comment this section out if you want to define specific restrictions.
		{"action": "accept", "src": ["*"], "dst": ["*:*"]},
	],

	// Define users and devices that can use Tailscale SSH.
	"ssh": [
		// Allow all users to SSH into their own devices in check mode.
		// Comment this section out if you want to define specific restrictions.
		{
			"action": "check",
			"src":    ["autogroup:members"],
			"dst":    ["autogroup:self"],
			"users":  ["autogroup:nonroot", "root"],
		},
	],

	// Test access rules every time they're saved.
	// "tests": [
	//  	{
	//  		"src": "alice@example.com",
	//  		"accept": ["tag:example"],
	//  		"deny": ["100.101.102.103:443"],
	//  	},
	// ],
}
```
Generate a tailscale auth key - https://login.tailscale.com/admin/settings/keys

Copy the auth key to the install_tailscale.sh.example script and rename it to install_tailscale.sh

Create a KeyPair for all VMs:
```bash
export REGION=ca-central-1
export MULTIREGION_PREFIX=bacalhau-multi-region-example
aws ec2 create-key-pair --key-name bacalhau-multi-region-example --query 'KeyMaterial' --output text --region $REGION > ~/.ssh/bacalhau-multi-region-example.pem
chmod 400 ~/.ssh/bacalhau-multi-region-example.pem
```

Create a VPC that can be used for the bootstrap VM, that can be accessed by anyone in the tailscale network.
```bash
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region $REGION \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=bacalhau-multi-region-example-bootstrap-vm}, {Key=Group,Value=bacalhau-multi-region-example}]'

Export the VPC_ID for later use:
```bash
export VPC_ID=vpc-0f2f30df79be600b3 # Will be output from previous command
```

Create an internet gateway for the VPC:
```bash
aws ec2 create-internet-gateway \
	--region $REGION \
	--tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=bacalhau-multi-region-example-igw}, {Key=Group,Value=bacalhau-multi-region-example}]'
```

Export the INTERNET_GATEWAY_ID for later use:
```bash
export INTERNET_GATEWAY_ID=igw-07ac9fafe64d182aa # Will be output from previous command
```

Attach internet gateway to VPC_ID:
```bash
aws ec2 attach-internet-gateway \
	--internet-gateway-id $INTERNET_GATEWAY_ID \
	--vpc-id $VPC_ID \
	--region $REGION
```

Create a route table that points to the public internet, that targets the whole VPC:
```bash
aws ec2 create-route-table \
	--vpc-id $VPC_ID \
	--region $REGION \
	--tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=bacalhau-multi-region-example-rtb}, {Key=Group,Value=bacalhau-multi-region-example}]'
```

Export the ROUTE_TABLE_ID for later use:
```bash
export ROUTE_TABLE_ID=rtb-085c5da95e6d150bc # Will be output from previous command
```
 
Create a route table association for the subnet:
```bash
aws ec2 associate-route-table \
	--route-table-id $ROUTE_TABLE_ID \
	--subnet-id $SUBNET_ID \
	--region $REGION
```

Export the ROUTE_TABLE_ASSOCIATION_ID for later use:
```bash
export ROUTE_TABLE_ASSOCIATION_ID=rtbassoc-08d080487318b9088 # Will be output from previous command
```

Create a route that points to the internet gateway:
```bash
aws ec2 create-route \
	--route-table-id $ROUTE_TABLE_ID \
	--destination-cidr-block 0.0.0.0/0 \
	--gateway-id $INTERNET_GATEWAY_ID \
	--region $REGION
```

Create a security group for a single VM that can be used as a bootstrap VM.
```bash
aws ec2 create-security-group \
  --description "Bacalhau Multi-Region Bootstrap Security Group" \
  --group-name bacalhau-multi-region-bootstrap-sg \
  --region $REGION \
  --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=bacalhau-multi-region-example-security-group}, {Key=Group,Value=bacalhau-multi-region-example}]'
```

Export the SECURITY_GROUP_ID for later use:
```bash
export SECURITY_GROUP_ID=sg-00038e2853c0344dc # Will be output from previous command
```

Create a subnet for the VM that can be made public.
```bash
export PUBLIC_CIDR_RANGE=10.0.1.0/24
aws ec2 create-subnet \
	--vpc-id $VPC_ID \
	--region $REGION \
	--cidr-block 10.0.1.0/24 \
	--tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=bacalhau-multi-region-example-subnet},{Key=Group,Value=bacalhau-multi-region-example}]'
```

Export the SUBNET_ID for later use:
```bash
export SUBNET_ID=subnet-0d9dca9d70f6d6703
```

Create a bootstrap VM manually with the AWS CLI and install tailscale on it.
```bash
# Create a bootstrap VM
aws ec2 run-instances \
  --region $REGION \
  --placement "AvailabilityZone=${REGION}a" \
  --image-id ami-0abc4c35ba4c005ca \
  --instance-type t3.small \
  --key-name bacalhau \
  --security-group-ids $SECURITY_GROUP_ID \
  --subnet-id $SUBNET_ID \
  --network-interfaces "DeviceIndex=0,AssociatePublicIpAddress=true" \
  --key-name bacalhau-multi-region-example \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=bacalhau-multi-region-example-bootstrap-vm}, {Key=Group,Value=bacalhau-multi-region-example}]'
```

Export the instance ID to use later:
```bash
export INSTANCE_ID=i-04f96aadaebfac404
```

Add the correct ingress/egress rules to the security group:
```bash
aws ec2 authorize-security-group-ingress \
        --region $REGION \
        --group-id $SECURITY_GROUP_ID \
        --ip-permissions IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges="[{CidrIp=0.0.0.0/0}]" \
        --tag-specifications 'ResourceType=security-group-rule,Tags=[{Key=Name,Value=bacalhau-multi-region-example-bootstrap-sg-rule}, {Key=Group,Value=bacalhau-multi-region-example}]'
```

Get the IP address of the VM and put it in a variable named BOOTSTRAP_IP_ADDRESS:
```bash
export BOOTSTRAP_IP_ADDRESS=$(aws ec2 describe-instances --region $REGION --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
```

Copy the scripts/* directory to the bootstrap VM:
```bash
scp -i ~/.ssh/bacalhau-multi-region-example.pem -r scripts ubuntu@$BOOTSTRAP_IP_ADDRESS:/home/ubuntu
```

Run the install script on the bootstrap VM:
```bash
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo /home/ubuntu/scripts/install-bacalhau.sh"
```

Run the install tailscale script on the VM and give it the hostname bacalhau-bootstrap-node:
```bash
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo /home/ubuntu/scripts/install-tailscale.sh --hostname=bacalhau-bootstrap-node"
```

Move the bacalhau.service file into systemd and start the service:
```bash
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo mv /home/ubuntu/scripts/bacalhau.service /etc/systemd/system/bacalhau.service"
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo systemctl daemon-reload"
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo systemctl enable bacalhau.service"
ssh -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS "sudo systemctl start bacalhau.service"
```

Copy the /run/bacalhau.run file to your local directory and put the absolute location in a variable named BACALHAU_RUN_FILE:
```bash
scp -i ~/.ssh/bacalhau-multi-region-example.pem ubuntu@$BOOTSTRAP_IP_ADDRESS:/run/bacalhau.run .
export BACALHAU_RUN_FILE=$(pwd)/bacalhau.run
```

Run terraform init:
```bash
terraform init
```

Run terraform apply:
```bash
terraform apply
```


On each VM:
* Get the service account credentials
* See if the secret exists and is not null
* If the secret is null, see if the lock file is present
* If the lock file is present, wait for 30 seconds and try again
* If the lock file is not present, set the lock file and start the server from scratch
* If the secret is not null, start the server from the secret