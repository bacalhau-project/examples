#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import json
import os
import yaml

def main():
    # Take the env variable for CONFIG_FILE and IDENTITY_FILE
    config_file = "/root/config.yaml"
    identity_file = "/root/node_identity.json"
    
    # Check to make sure config.yaml and node_identity.json exist
    if not os.path.exists(config_file):
        print("config.yaml does not exist")
        exit(1)
    if not os.path.exists(identity_file):
        print("node_identity.json does not exist")
        exit(1)
    
    # Load the config and identity files
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    with open(identity_file, "r") as f:
        identity = json.load(f)
    
    # Verify both files have location data
    if not identity.get("location"):
        print("node_identity.json does not contain a location")
        exit(1)
    
    # Respond with a json object with the following fields:
    # - config_file
    # - identity_file
    # - location
    # - latitude
    # - longitude
    print(json.dumps({
        "config_file": config_file,
        "identity_file": identity_file,
        "location": identity["location"],
        "latitude": identity["latitude"],
        "longitude": identity["longitude"]
    }))

if __name__ == "__main__":
    main()
