#!env python3
import argparse
import boto3
import json
import requests

parser = argparse.ArgumentParser(description='Get latest AMIs from Canonical.')
parser.add_argument('--owner', default='099720109477', help='The owner of the AMI. Default is Canonical.')
parser.add_argument('--architecture', default='x86_64', help='The architecture of the AMI. Default is x86_64.')
parser.add_argument('--name', default='*ubuntu-20.04*', help='The name pattern of the AMI. Default is *ubuntu-20.04*.')

args = parser.parse_args()

def get_latest_ubuntu_ami(region):
    ec2 = boto3.client("ec2", region_name=region)
    response = ec2.describe_images(
        Owners=[args.owner],  
        Filters=[{"Name": "architecture", "Values": [args.architecture]}, {"Name": "name", "Values": [args.name]}],
    )

    # Sort on creation date and select the most recent
    amis = sorted(response["Images"], key=lambda k: k["CreationDate"], reverse=True)
    if amis:
        return amis[0]["ImageId"]
    else:
        return None

request_url = "https://cloud-images.ubuntu.com/locator/ec2/releasesTable"
response = requests.get(request_url)
if response.status_code != 200:
    raise Exception(f"Request to {request_url} failed with status code {response.status_code}")

# Parse the response
data = json.loads(response.text)["aaData"]

# Filter to only Ubuntu 20.04 LTS, the second column
data = [row for row in data if row[2] == "20.04 LTS" and row[3] == "amd64"]

completeAMIList = {}
for row in data:
    region = row[0]
    zone = row[0] + "a"
    ami = row[6].split(">")[1].split("<")[0]
    completeAMIList[region] = {"region": region, "zone": zone, "instance_ami": ami}

# Load initial JSON blob
with open("regions.md", "r") as f:
    # Skip first line
    f.readline()
    # Load the text from the markdown file, where each line is a region, and remove # at the front (if present)
    regions = {line.strip("#").strip(): {} for line in f.readlines()}

# Update each region with the latest Ubuntu 20.04 AMI
outputLocations = {}
for region in regions:
    try:
        outputLocations[region] = completeAMIList[region]
    except KeyError:
        print(f"Warning: No AMI data found for region '{region}'. Skipping this region.")

# Save updated JSON blob
with open("regions.json", "w") as f:
    print(json.dumps(outputLocations, indent=4))
