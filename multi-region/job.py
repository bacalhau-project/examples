import json
import concurrent.futures
import subprocess
import argparse

def run_command(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode

# Create the parser
parser = argparse.ArgumentParser(description="Execute docker commands")

# Add the arguments
parser.add_argument('--prompt_value', type=str, help="The prompt value for the Docker command", default='person')

# Parse the arguments
args = parser.parse_args()

# Load the .env.json file
with open('./tf/.env.json') as json_file:
    data = json.load(json_file)

# Extract app_tag
app_tag = data["app_tag"]

# Create an empty list to hold the commands
commands = []

# Iterate through the regions
for region in data["locations"].keys():
    # Define input and output bucket names
    input_bucket = f'{app_tag}-{region}-images-bucket'
    output_bucket = f'{app_tag}-{region}-o-images-bucket'

    # Format the Docker run command
    command = (f'bacalhau docker run --gpu 1 -i src=s3://{input_bucket}/*,opt=region={region} '
               f'-p s3://{output_bucket}/*,opt=region={region} -s region={region} '
               f'expanso/sam:new -- /bin/bash -c \'python /sam.py --input "/inputs" '
               f'--output "/outputs" --prompt "{args.prompt_value}"\'')
    
    # Add command to the list
    commands.append(command)

# Execute the commands in parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    results = list(executor.map(run_command, commands))

# Print results
for command, result in zip(commands, results):
    stdout, stderr, returncode = result
    print(f"Command: {command}\nSTDOUT: {stdout}\nSTDERR: {stderr}\nReturn Code: {returncode}\n")
