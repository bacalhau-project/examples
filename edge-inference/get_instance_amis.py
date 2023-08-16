import boto3
import argparse
import json

def get_ami_details(name):
    # read the regions from the file, skipping the first two lines
    with open("regions.md", "r") as file:
        regions = file.readlines()[2:]
    regions = [region.strip() for region in regions]  # remove newline characters

    ami_details = {}
    for region in regions:
        ec2 = boto3.resource('ec2', region_name=region)
        images = ec2.images.filter(Filters=[{'Name':'name', 'Values':[name]}])

        for image in images:
            ami_details[region] = {
                "region": region,
                "zone": region + "a",  # assuming zone 'a' for simplicity
                "instance_ami": image.id,
            }

    return ami_details

def pretty_print(data):
    print(json.dumps(data, indent=4))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get latest AMIs from a specific name pattern.')
    parser.add_argument('--name', default='Deep Learning AMI GPU PyTorch 2.0.1 (Ubuntu 20.04) 20230620', help='The name pattern of the AMI.')
    args = parser.parse_args()

    ami_details = get_ami_details(args.name)
    pretty_print(ami_details)
