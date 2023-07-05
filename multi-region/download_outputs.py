import json
import argparse
import subprocess

def extract_buckets_and_regions():
    # Load the .env.json file
    with open('./tf/.env.json') as json_file:
        data = json.load(json_file)

    # Extract app_tag
    app_tag = data["app_tag"]

    # Define a list to store the bucket names and regions
    bucket_region_pairs = []

    # Iterate through the regions
    for region in data["locations"].keys():
        # Format the string
        bucket_name = f'{app_tag}-{region}-o-images-bucket'
        
        # Append the bucket name and region to the list as a tuple
        bucket_region_pairs.append((bucket_name, region))

    return bucket_region_pairs

def download_buckets_content(bucket_region_pairs, download_path):
    # Iterate over the bucket and region pairs
    for bucket, region in bucket_region_pairs:
        # Form the AWS CLI command
        command = f"aws s3 sync s3://{bucket}/*/outputs/ {download_path} --region {region}"
        
        # Execute the command
        try:
            subprocess.check_call(command, shell=True)
            print(f"Successfully downloaded contents from bucket: {bucket}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to download contents from bucket: {bucket}. Error: {str(e)}")

# Create the parser
parser = argparse.ArgumentParser(description="Download files from AWS S3 buckets")

# Add the arguments
parser.add_argument('download_path', type=str, help="The path where the files will be downloaded")

# Parse the arguments
args = parser.parse_args()

# Call the function to get the bucket and region pairs
bucket_region_pairs = extract_buckets_and_regions()

# Download the contents from the buckets
download_buckets_content(bucket_region_pairs, args.download_path)