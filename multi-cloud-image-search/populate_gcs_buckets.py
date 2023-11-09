import argparse
import os
import json
import random
from google.cloud import storage
from google.cloud.exceptions import NotFound

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

def check_buckets_and_objects(storage_client, src_bucket_name, dst_bucket_names, object_name):
    # Check if source bucket exists
    try:
        source_bucket = storage_client.get_bucket(src_bucket_name)
        print(f"Source bucket {src_bucket_name} found.")
    except NotFound:
        print(f"Source bucket {src_bucket_name} does not exist.")
        return False

    # Check if source object exists
    source_blob = source_bucket.blob(object_name)
    if not source_blob.exists():
        print(f"Object {object_name} does not exist in source bucket {src_bucket_name}.")
        return False
    else:
        print(f"Object {object_name} found in source bucket {src_bucket_name}.")

    # Check if destination buckets exist
    for dst_bucket_name in dst_bucket_names:
        try:
            storage_client.get_bucket(dst_bucket_name)
            print(f"Destination bucket {dst_bucket_name} found.")
        except NotFound:
            print(f"Destination bucket {dst_bucket_name} does not exist.")
            return False
    return True

def copy_random_images_to_gcs_buckets(src_bucket_name, dst_bucket_names, storage_client, sample_size):
    source_bucket = storage_client.get_bucket(src_bucket_name)
    blobs = list(source_bucket.list_blobs())
    all_images = [blob.name for blob in blobs if blob.name.endswith(('.png', '.jpg', '.jpeg'))]

    for dst_bucket_name in dst_bucket_names:
        destination_bucket = storage_client.get_bucket(dst_bucket_name)
        if len(all_images) < sample_size:
            print(f"Not enough images in source bucket to sample. Found {len(all_images)} image(s).")
            return

        sample_images = random.sample(all_images, sample_size)
        for image_name in sample_images:
            source_blob = source_bucket.blob(image_name)
            destination_blob = destination_bucket.blob(image_name)
            # Use rewrite instead of copy_blob
            token = None
            while True:
                print(f"Attempting to copy {image_name} to {dst_bucket_name}")
                token, _, _ = destination_blob.rewrite(source_blob, token=token)
                if token is None:
                    break
            print(f"Successfully copied {image_name} from {src_bucket_name} to {dst_bucket_name}")


def retrieve_gcs_bucket_info(src_bucket_name, sample_size):
    storage_client = storage.Client()

    dst_bucket_names = extract_regions_and_store()

    # Perform checks before proceeding
    if not check_buckets_and_objects(storage_client, src_bucket_name, dst_bucket_names, 'dog.81.jpg'):
        print("One or more checks failed. Exiting the script.")
        return

    copy_random_images_to_gcs_buckets(src_bucket_name, dst_bucket_names, storage_client, sample_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve GCS bucket information using Terraform and copy a random set of images from a source GCS bucket.")

    parser.add_argument("--sample_size", type=int, default=10,
                        help="Number of images to sample from the source GCS bucket. Default: 10")

    args = parser.parse_args()
    src_bucket_name = "sea_creatures"

    retrieve_gcs_bucket_info(src_bucket_name, args.sample_size)
