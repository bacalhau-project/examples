import json
import subprocess
import argparse

def extract_buckets_and_regions():
    with open('./tf/.env.json') as json_file:
        data = json.load(json_file)

    app_tag = data["app_tag"]
    bucket_region_pairs = []

    for region in data["locations"].keys():
        bucket_name = f'{app_tag}-{region}-o-images-bucket'
        bucket_region_pairs.append((bucket_name, region))

    return bucket_region_pairs

def sync_to_specified_bucket(bucket_region_pairs, target_bucket, target_region):
    bucket_region_pairs.remove((target_bucket, target_region))
    
    for source_bucket, source_region in bucket_region_pairs:
        command = f"aws s3 sync s3://{source_bucket}/*/outputs/ s3://{target_bucket}/gradients --source-region {source_region}"
        
        try:
            subprocess.check_call(command, shell=True)
            print(f"Successfully synced contents from bucket: {source_bucket} to {target_bucket}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to sync contents from bucket: {source_bucket} to {target_bucket}. Error: {str(e)}")

    print(f"\nAll gradients synced to bucket: {target_bucket} in region: {target_region}")
    return target_bucket, target_region

def run_docker_commands(target_bucket, target_region):
    command = (f'bacalhau docker run --gpu 1 -i s3://{target_bucket}/gradients/*,opt=region={target_region} '
               f'-p s3://{target_bucket}/*,opt=region={target_region} -s region={target_region} '
               f'expanso/federated:new -- python update_model.py --model_path brain_tumor_classifier.h5'
               f'--saved_gradients /inputs --dataset_path brain-tumor-train.csv --save_path /outputs/brain_tumor_classifier_updated.h5')
    
    stdout, stderr, returncode = run_command(command)

    print(f"Command: {command}\nSTDOUT: {stdout.decode('utf-8')}\nSTDERR: {stderr.decode('utf-8')}\nReturn Code: {returncode}\n")

def run_command(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sync gradients to a specified bucket and run Docker commands.')
    parser.add_argument('--target_bucket', type=str, required=True, help='Target bucket to which gradients will be synced.')
    parser.add_argument('--target_region', type=str, required=True, help='AWS region of the target bucket.')

    args = parser.parse_args()
    
    bucket_region_pairs = extract_buckets_and_regions()
    sync_to_specified_bucket(bucket_region_pairs, args.target_bucket, args.target_region)
    run_docker_commands(args.target_bucket, args.target_region)
