import collections
import csv
import logging
import os
from importlib import import_module

import yaml

from util.scripts_provider import ScriptsProvider


class Config(collections.OrderedDict):
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

    def get_region_configs(self):
        regions = self.get("regions", [])
        aggregated_regions = []

        for region in regions:
            region_name = next(iter(region))
            if region_name not in aggregated_regions:
                aggregated_regions.append()[region_name] = []

            aggregated_regions[region_name].append(region[region_name])

        return aggregated_regions

    def get_region_config(self, region_name):
        result = []
        regions = self.get("regions", [])
        for region in regions:
            name = next(iter(region))
            if region_name == name:
                result.append(region)
        return result

    def get_scripts_provider(self, region_name, region_cfg, node_idx):
        # Construct the module name and class name dynamically
        scripts_provider_name = region_cfg.get("cloud-init-scripts", "default")

        if scripts_provider_name == "default":
            logging.debug(
                f"region: {region_name}, node: {node_idx + 1}, arch: {region_cfg.get('architecture', 'x86_64')}, class: ScriptsProvider")
            return ScriptsProvider(self)

        module_name = f"instance.{scripts_provider_name.lower()}.scripts_provider"
        class_name = f"{scripts_provider_name.capitalize()}ScriptsProvider"
        logging.debug(
            f"region: {region_name}, node: {node_idx + 1}, arch: {region_cfg.get('architecture', 'x86_64')}, class: {class_name}")
        try:
            module = import_module(module_name)
            cls = getattr(module, class_name)
            instance = cls(self)
            return instance

        except (ModuleNotFoundError, AttributeError) as e:
            raise ImportError(f"Failed to import or instantiate {class_name}: {str(e)}")

    def get_amis_file_path(self):
        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(parent_dir, "ubuntu_amis.csv")

    def get_image_for_region(self, region_name, region_config):
        architecture = region_config.get("architecture", "x86_64")
        ami_value = region_config.get("image")
        if ami_value != "auto":
            return ami_value

        amis_file = self.get_amis_file_path()

        if not os.path.exists(amis_file):
            raise FileNotFoundError(f"AMI file '{amis_file}' not found.")

        with open(amis_file, mode="r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["Region"] == region_name and row["Architecture"] == architecture:
                    return row["AMI ID"]

        raise ValueError(f"No AMI found for region '{region_name}' and architecture '{architecture}' in '{amis_file}'.")

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

    def get_env_for_region(self, region_cfg):
        return ' '.join(region_cfg.get("env", []))
