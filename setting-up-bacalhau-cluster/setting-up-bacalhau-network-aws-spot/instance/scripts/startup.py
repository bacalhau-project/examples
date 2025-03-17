#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "pyyaml",
# ]
# ///

import os
import subprocess

import requests
import yaml

BACALHAU_NODE_DIR = os.getenv("BACALHAU_NODE_DIR", "/bacalhau_node")


def get_cloud_metadata():
    cloud = subprocess.getoutput("cloud-init query cloud-name")
    metadata = {}

    if cloud == "gce":
        print("Detected GCP environment")
        metadata["CLOUD_PROVIDER"] = "GCP"
        zone_info = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/zone",
            headers={"Metadata-Flavor": "Google"},
        ).text
        metadata["REGION"] = zone_info.split("/")[3]
        metadata["ZONE"] = zone_info.split("/")[3]
        metadata["PUBLIC_IP"] = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip",
            headers={"Metadata-Flavor": "Google"},
        ).text
        metadata["PRIVATE_IP"] = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip",
            headers={"Metadata-Flavor": "Google"},
        ).text
        metadata["INSTANCE_ID"] = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/id",
            headers={"Metadata-Flavor": "Google"},
        ).text
        metadata["INSTANCE_TYPE"] = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/machine-type",
            headers={"Metadata-Flavor": "Google"},
        ).text.split("/")[-1]
        metadata["PROJECT_ID"] = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        ).text
    elif cloud == "aws":
        print("Detected AWS environment")
        metadata["CLOUD_PROVIDER"] = "AWS"
        token = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        ).text
        headers = {"X-aws-ec2-metadata-token": token}
        metadata["REGION"] = requests.get(
            "http://169.254.169.254/latest/meta-data/placement/region", headers=headers
        ).text
        metadata["ZONE"] = requests.get(
            "http://169.254.169.254/latest/meta-data/placement/availability-zone",
            headers=headers,
        ).text
        metadata["PUBLIC_IP"] = requests.get(
            "http://169.254.169.254/latest/meta-data/public-ipv4", headers=headers
        ).text
        metadata["PRIVATE_IP"] = requests.get(
            "http://169.254.169.254/latest/meta-data/local-ipv4", headers=headers
        ).text
        metadata["INSTANCE_ID"] = requests.get(
            "http://169.254.169.254/latest/meta-data/instance-id", headers=headers
        ).text
        metadata["INSTANCE_TYPE"] = requests.get(
            "http://169.254.169.254/latest/meta-data/instance-type", headers=headers
        ).text
    elif cloud == "azure":
        print("Detected Azure environment")
        metadata["CLOUD_PROVIDER"] = "AZURE"
        azure_metadata = requests.get(
            "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
            headers={"Metadata": "true"},
        ).json()
        metadata["REGION"] = azure_metadata["compute"]["location"]
        metadata["ZONE"] = azure_metadata["compute"]["zone"]
        metadata["PUBLIC_IP"] = requests.get("https://ip.me").text.strip()
        metadata["PRIVATE_IP"] = azure_metadata["network"]["interface"][0]["ipv4"][
            "ipAddress"
        ][0]["privateIpAddress"]
        metadata["INSTANCE_ID"] = azure_metadata["compute"]["vmId"]
        metadata["INSTANCE_TYPE"] = azure_metadata["compute"]["vmSize"]
    else:
        print("Could not detect cloud provider - no node info will be set")
        return {}

    return metadata


def add_label(key, value):
    config_file = os.path.join(BACALHAU_NODE_DIR, "config.yaml")

    with open(config_file, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)

    if "Labels" not in data:
        data["Labels"] = {}

    data["Labels"][key] = value

    with open(config_file, "w") as f:
        yaml.dump(data, f)


def main():
    metadata = get_cloud_metadata()
    if not metadata:
        return

    with open(os.path.join(BACALHAU_NODE_DIR, "node-info"), "w") as f:
        for key, value in metadata.items():
            f.write(f"{key}={value}\n")

    if metadata["CLOUD_PROVIDER"] == "GCP":
        with open(os.path.join(BACALHAU_NODE_DIR, "node-info"), "a") as f:
            f.write(f"PROJECT_ID={metadata['PROJECT_ID']}\n")

    with open(os.path.join(BACALHAU_NODE_DIR, "node-info"), "r") as f:
        for line in f:
            key, value = line.strip().split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                print(f"Adding label: {key}: {value}")
                add_label(key, value)

    print("Verifying Docker service...")
    if subprocess.run(["systemctl", "is-active", "--quiet", "docker"]).returncode != 0:
        print("Docker is not running. Starting Docker...")
        subprocess.run(["systemctl", "start", "docker"], check=True)
        import time

        time.sleep(5)

    print("Setting up configuration...")
    config_file = os.path.join(BACALHAU_NODE_DIR, "config.yaml")
    if not os.path.isfile(config_file):
        print(f"Error: Configuration file not found at {config_file}")
        exit(1)

    print("Starting Docker Compose services...")
    compose_file = os.path.join(BACALHAU_NODE_DIR, "docker-compose.yaml")
    if os.path.isfile(compose_file):
        os.chdir(BACALHAU_NODE_DIR)
        print("Stopping and removing any existing containers...")
        subprocess.run(["docker", "compose", "down"], check=True)
        if (
            subprocess.run(
                ["docker", "ps", "-a"], capture_output=True, text=True
            ).stdout.count("bacalhau_node-bacalhau-node")
            > 0
        ):
            print("Found stray containers, removing them...")
            subprocess.run(
                "docker ps -a | grep 'bacalhau_node-bacalhau-node' | awk '{print $1}' | xargs -r docker rm -f",
                shell=True,
                check=True,
            )
        print("Pulling latest images...")
        subprocess.run(["docker", "compose", "pull"], check=True)
        print("Starting services...")
        subprocess.run(["docker", "compose", "up", "-d"], check=True)
        print("Docker Compose started.")
    else:
        print(f"Error: docker-compose.yaml not found at {compose_file}")
        exit(1)

    print(
        f"Bacalhau node setup complete in {metadata['CLOUD_PROVIDER']} region {metadata['REGION']}"
    )
    print(f"Public IP: {metadata['PUBLIC_IP']}")
    print(f"Private IP: {metadata['PRIVATE_IP']}")


if __name__ == "__main__":
    main()
