import argparse
import os
import json
import random
import boto3

def extract_regions_and_store():
    # Load the .env.json file
    with open('./tf/aws/.env.json') as json_file:
        data = json.load(json_file)

    # Extract app_tag
    app_tag = data["app_tag"]

    # Store the formatted strings in a list
    bucket_names = []
    # Iterate through the regions
    for region in data["locations"].keys():
        # Format the string and add it to the list
        bucket_names.append(f'{app_tag}-{region}-images-bucket')

    return bucket_names

def copy_random_images_to_s3_buckets(src_bucket_name, dst_bucket_names, s3, sample_size):
    all_objects = s3.list_objects(Bucket=src_bucket_name)['Contents']
    all_images = [obj['Key'] for obj in all_objects if obj['Key'].endswith(('.png', '.jpg', '.jpeg'))]

    for dst_bucket_name in dst_bucket_names:
        sample_images = random.sample(all_images, sample_size)
        for image_name in sample_images:
            copy_source = {
                'Bucket': src_bucket_name,
                'Key': image_name
            }
            s3.copy(copy_source, dst_bucket_name, image_name)
            print(f"Copied {image_name} from {src_bucket_name} to {dst_bucket_name}")

def retrieve_s3_bucket_info(src_bucket_name, sample_size):
    s3 = boto3.client("s3", region_name="us-east-1")

    dst_bucket_names = extract_regions_and_store()

    copy_random_images_to_s3_buckets(src_bucket_name, dst_bucket_names, s3, sample_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve S3 bucket information using Terraform and copy a random set of images from a source S3 bucket.")

    parser.add_argument("--sample_size", type=int, default=10, 
                        help="Number of images to sample from the source S3 bucket. Default: 10")

    args = parser.parse_args()
    src_bucket_name = "sea-creatures"
    
    retrieve_s3_bucket_info(src_bucket_name, args.sample_size)
