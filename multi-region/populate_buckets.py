import argparse
import os
import json
import random
import boto3
import terraform

def populate_s3_buckets(bucket_names, image_dir, sample_size):
    s3 = boto3.client("s3")

    for bucket_name in bucket_names:
        files = os.listdir(image_dir)
        sample_files = random.sample(files, sample_size)

        for file_name in sample_files:
            file_path = os.path.join(image_dir, file_name)
            s3.upload_file(file_path, bucket_name, file_name)
            print(f"Uploaded {file_name} to {bucket_name}")

def retrieve_s3_bucket_info(working_dir, sample_size):
    # Initialize the Terraform API
    tf = terraform.Terraform(working_dir)

    # Run 'terraform init' to initialize the working directory
    tf.init()

    # Run 'terraform refresh' to update the state file
    tf.refresh()

    # Get the Terraform state
    state = tf.state()

    # Retrieve information about S3 buckets
    s3_buckets = state.get_resources_by_type("aws_s3_bucket")

    # Extract the bucket names
    bucket_names = [bucket["name"] for bucket in s3_buckets]

    # Populate S3 buckets with images
    image_dir = "/path/to/coco/validation/images"  # Path to the COCO validation image directory
    populate_s3_buckets(bucket_names, image_dir, sample_size)

if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Retrieve S3 bucket information using Terraform and populate with COCO dataset images.")

    # Add the working_dir argument with a default value of the current working directory
    parser.add_argument("working_dir", type=str, nargs="?", default=os.getcwd(),
                        help="Path to the Terraform working directory. Default: current working directory")

    # Add the sample_size argument with a default value of 10
    parser.add_argument("--sample_size", type=int, default=10,
                        help="Number of images to sample from the COCO dataset. Default: 10")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the function with the provided working directory and sample size
    retrieve_s3_bucket_info(args.working_dir, args.sample_size)
