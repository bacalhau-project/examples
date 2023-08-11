import json
import subprocess
import random
import concurrent.futures

def extract_buckets_and_regions():
    with open('./tf/.env.json') as json_file:
        data = json.load(json_file)

    app_tag = data["app_tag"]
    bucket_region_pairs = []

    for region in data["locations"].keys():
        bucket_name = f'{app_tag}-{region}-o-images-bucket'
        bucket_region_pairs.append((bucket_name, region))

    return bucket_region_pairs

def sync_to_random_bucket(bucket_region_pairs):
    target_bucket, target_region = random.choice(bucket_region_pairs)
    bucket_region_pairs.remove((target_bucket, target_region))
    
    for source_bucket, source_region in bucket_region_pairs:
        command = f"aws s3 sync s3://{source_bucket}/*/outputs/ s3://{target_bucket}/ --source-region {source_region}"
        
        try:
            subprocess.check_call(command, shell=True)
            print(f"Successfully synced contents from bucket: {source_bucket} to {target_bucket}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to sync contents from bucket: {source_bucket} to {target_bucket}. Error: {str(e)}")

    print(f"\nAll gradients synced to bucket: {target_bucket} in region: {target_region}")
    return target_bucket, target_region

def run_docker_commands(target_bucket, target_region):
    command = (f'bacalhau docker run --gpu 1 -i s3://{target_bucket}/*,opt=region={target_region} '
               f'-p s3://{target_bucket}/*,opt=region={target_region} -s region={target_region} '
               f'expanso/federated -- python update_model.py --model_path model.h5 '
               f'--saved_gradients /inputs --dataset_path brain-tumor-train.csv')
    
    stdout, stderr, returncode = run_command(command)

    print(f"Command: {command}\nSTDOUT: {stdout.decode('utf-8')}\nSTDERR: {stderr.decode('utf-8')}\nReturn Code: {returncode}\n")

def run_command(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode

if __name__ == "__main__":
    bucket_region_pairs = extract_buckets_and_regions()
    target_bucket, target_region = sync_to_random_bucket(bucket_region_pairs)
    run_docker_commands(target_bucket, target_region)
