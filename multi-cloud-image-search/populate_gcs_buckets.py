import argparse
import os
import json
import random
from google.cloud import storage

def extract_regions_and_store():
    # Load the .env.json file
    with open('./tf/gcp/.env.json') as json_file:
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

def copy_random_images_to_gcs_buckets(src_bucket_name, dst_bucket_names, storage_client, sample_size):
    source_bucket = storage_client.get_bucket(src_bucket_name)
    blobs = list(source_bucket.list_blobs())
    all_images = [blob.name for blob in blobs if blob.name.endswith(('.png', '.jpg', '.jpeg'))]

    for dst_bucket_name in dst_bucket_names:
        destination_bucket = storage_client.get_bucket(dst_bucket_name)
        sample_images = random.sample(all_images, sample_size)
        for image_name in sample_images:
            source_blob = source_bucket.blob(image_name)
            destination_blob = destination_bucket.blob(image_name)
            storage_client.copy_blob(source_blob, destination_bucket, image_name)
            print(f"Copied {image_name} from {src_bucket_name} to {dst_bucket_name}")

def retrieve_gcs_bucket_info(src_bucket_name, sample_size):
    storage_client = storage.Client()

    dst_bucket_names = extract_regions_and_store()

    copy_random_images_to_gcs_buckets(src_bucket_name, dst_bucket_names, storage_client, sample_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve GCS bucket information using Terraform and copy a random set of images from a source GCS bucket.")

    parser.add_argument("--sample_size", type=int, default=10,
                        help="Number of images to sample from the source GCS bucket. Default: 10")

    args = parser.parse_args()
    src_bucket_name = "sea-creatures"

    retrieve_gcs_bucket_info(src_bucket_name, args.sample_size)
