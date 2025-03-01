import csv
import os

import yaml


class Config(dict):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self._load_yaml()

    def _load_yaml(self):
        with open(self.file_path, "r") as file:
            self.update(yaml.safe_load(file))  # Load YAML as a dictionary

    def get_regions(self):
        return [list(region.keys())[0] for region in self.get("regions", [])]

    def get_total_instances(self):
        return self.get("max_instances", 0)

    def get_ssh_keypair(self):
        return self.get("ssh_key_name")

    def get_region_config(self, region_name):
        for region in self.get("regions", []):
            if region_name in region:
                return region[region_name]
        return None

    def get_amis_file_path(self):
        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(parent_dir, "ubuntu_amis.csv")


    def get_image_for_region(self, region_name):
        region_config = self.get_region_config(region_name)
        if not region_config:
            raise ValueError(f"Region '{region_name}' not found in config.")

        ami_value = region_config.get("image")
        if ami_value != "auto":
            return ami_value

        amis_file = self.get_amis_file_path()

        if not os.path.exists(amis_file):
            raise FileNotFoundError(f"AMI file '{amis_file}' not found.")

        with open(amis_file, mode="r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["Region"] == region_name:
                    return row["AMI ID"]

        raise ValueError(f"No AMI found for region '{region_name}' in '{amis_file}'.")

    def get_orchestrators(self):
        return self.get("orchestrators", [])

    def get_token(self):
        return self.get("token")

    def get_tls(self):
        return self.get("tls", False)

    def get_tls(self):
        return self.get("tls", False)

    def get_public_ssh_key_path(self):
        return self.get("public_ssh_key_path", "")

    def get_username(self):
        return self.get("username", "bacalhau-runner")
