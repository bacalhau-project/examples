import argparse
import os
import json
import random
import boto3
import terraform

def copy_random_images_to_s3_buckets(src_bucket_name, dst_bucket_names, s3, sample_size):
    all_objects = s3.list_objects(Bucket=src_bucket_name)['Contents']
    all_images = [obj['Key'] for obj in all_objects if obj['Key'].endswith(('.png', '.jpg', '.jpeg'))]
    sample_images = random.sample(all_images, sample_size)

    for dst_bucket_name in dst_bucket_names:
        for image_name in sample_images:
            copy_source = {
                'Bucket': src_bucket_name,
                'Key': image_name
            }
            s3.copy(copy_source, dst_bucket_name, image_name)
            print(f"Copied {image_name} from {src_bucket_name} to {dst_bucket_name}")

def retrieve_s3_bucket_info(src_bucket_name, working_dir, sample_size):
    s3 = boto3.client("s3", region_name="eu-north-1")
    tf = terraform.Terraform(working_dir)
    tf.init()
    tf.refresh()

    state = tf.state()
    s3_buckets = state.get_resources_by_type("aws_s3_bucket")
    dst_bucket_names = [bucket["name"] for bucket in s3_buckets]

    copy_random_images_to_s3_buckets(src_bucket_name, dst_bucket_names, s3, sample_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve S3 bucket information using Terraform and copy a random set of images from a source S3 bucket.")

    parser.add_argument("working_dir", type=str, nargs="?", default=os.getcwd(), 
                        help="Path to the Terraform working directory. Default: current working directory")
    parser.add_argument("--sample_size", type=int, default=10, 
                        help="Number of images to sample from the source S3 bucket. Default: 10")

    args = parser.parse_args()
    src_bucket_name = "sam-coco"
    
    retrieve_s3_bucket_info(src_bucket_name, args.working_dir, args.sample_size)
