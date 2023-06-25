#!env python3
import boto3
import json
import requests


def get_latest_ubuntu_ami(region):
    ec2 = boto3.client("ec2", region_name=region)
    response = ec2.describe_images(
        Owners=["099720109477"],  # Canonical
        Filters=[{"Name": "architecture", "Values": ["x86_64"]}, {"Name": "name", "Values": ["*ubuntu-20.04*"]}],
    )

    # Sort on creation date and select the most recent
    amis = sorted(response["Images"], key=lambda k: k["CreationDate"], reverse=True)
    if amis:
        return amis[0]["ImageId"]
    else:
        return None


# Curl the following URL to get all AMIs
# curl -s "https://cloud-images.ubuntu.com/locator/ec2/releasesTable"
request_url = "https://cloud-images.ubuntu.com/locator/ec2/releasesTable"
response = requests.get(request_url)
if response.status_code != 200:
    raise Exception(f"Request to {request_url} failed with status code {response.status_code}")

# Parse the response
data = json.loads(response.text)["aaData"]

# Filter to only Ubuntu 20.04 LTS, the second column
data = [row for row in data if row[2] == "20.04 LTS" and row[3] == "amd64"]

# Create a dictionary of regions and their AMIs
# Output should look like this:
# "sa-east-1": {
#   "region": "sa-east-1",
#   "zone": "sa-east-1a",
#   "instance_ami": "ami-0af6e9042ea5a4e3e"
# },
# The instance AMI value is in the 7th column and looks like this:
# "<a href=\"https://console.aws.amazon.com/ec2/home?region=us-east-1#launchAmi=ami-0d65710e46db3c637\">ami-0d65710e46db3c637</a>",

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
    outputLocations[region] = completeAMIList[region]

# Save updated JSON blob
with open("regions.json", "w") as f:
    print(json.dumps(outputLocations, indent=4))
