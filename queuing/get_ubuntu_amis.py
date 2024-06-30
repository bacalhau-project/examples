import boto3

# List of all AWS regions
regions = [
    "us-west-2",
    "us-east-1",
    "eu-west-1",
    "ap-southeast-1",
    "sa-east-1",
    "eu-central-1",
    "ap-northeast-1",
    "ap-southeast-2",
    "ca-central-1",
    "eu-west-2",
]

# Dictionary to store the AMIs
UBUNTU_AMIS = {}


# Function to get the latest Ubuntu 22.04 LTS AMI ID in a region
def get_latest_ubuntu_ami(region):
    client = boto3.client("ec2", region_name=region)
    response = client.describe_images(
        Owners=["099720109477"],  # Canonical's AWS account ID
        Filters=[
            {
                "Name": "name",
                "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
            },
            {"Name": "architecture", "Values": ["x86_64"]},
            {"Name": "root-device-type", "Values": ["ebs"]},
            {"Name": "virtualization-type", "Values": ["hvm"]},
        ],
        MaxResults=1000,  # Ensure we get a sufficient number of results
    )
    # Sort images by creation date
    images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)
    return images[0]["ImageId"]


# Loop through each region and get the AMI ID
for region in regions:
    ami_id = get_latest_ubuntu_ami(region)
    UBUNTU_AMIS[region] = ami_id

# Print the AMIs in the desired structure
print("UBUNTU_AMIS = {")
for region, ami_id in UBUNTU_AMIS.items():
    print(f'    "{region}": "{ami_id}",')
print("}")
