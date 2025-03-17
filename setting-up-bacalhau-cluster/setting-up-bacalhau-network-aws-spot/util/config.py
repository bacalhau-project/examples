import csv
import logging
import os
from importlib import import_module

import yaml

from util.scripts_provider import ScriptsProvider

logger = logging.getLogger(__name__)


class Config(dict):
    def __init__(self, file_path):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Initializing Config with file_path: {file_path}")
        super().__init__()
        self.file_path = file_path
        self._load_yaml()
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug("Config initialization completed")

    def _load_yaml(self):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Loading YAML from {self.file_path}")
        try:
            with open(self.file_path, "r") as file:
                config_data = yaml.safe_load(file)
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    logger.debug(f"Loaded config data: {config_data}")
                self.update(config_data)
        except Exception as e:
            logger.error(
                f"Error loading config file {self.file_path}: {str(e)}", exc_info=True
            )
            raise

    def get_regions(self):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug("Getting regions from config")
        regions = [list(region.keys())[0] for region in self.get("regions", [])]
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Found regions: {regions}")
        return regions

    def get_total_instances(self):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug("Getting total instances from config")
        total = self.get("max_instances", 0)
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Total instances: {total}")
        return total

    def get_ssh_keypair(self):
        return self.get("ssh_key_name")

    def get_region_config(self, region_name):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Getting config for region: {region_name}")
        for region in self.get("regions", []):
            if region_name in region:
                config = region[region_name]
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    logger.debug(f"Found config for {region_name}: {config}")
                return config
        logger.warning(f"No config found for region: {region_name}")
        return None

    def get_scripts_provider_name(self, region_name, node_idx):
        scripts = self.get('cloud_init_scripts', {})
        script_key = f"{region_name}-node{node_idx + 1}"
        scripts_provider_name = scripts.get(script_key, "default")
        return scripts_provider_name

    def get_scripts_provider(self, region_name, node_idx):
        # Construct the module name and class name dynamically
        scripts_provider_name = self.get_scripts_provider_name(region_name, node_idx)

        if scripts_provider_name == "default":
            return ScriptsProvider(self)

        module_name = f"instance.{scripts_provider_name.lower()}.scripts_provider"
        class_name = f"{scripts_provider_name}ScriptsProvider"
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

    def get_image_for_region(self, region_name):
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Getting image for region: {region_name}")
        region_config = self.get_region_config(region_name)
        if not region_config:
            logger.error(f"Region '{region_name}' not found in config")
            raise ValueError(f"Region '{region_name}' not found in config.")

        ami_value = region_config.get("image")
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"AMI value from config: {ami_value}")

        if ami_value != "auto":
            return ami_value

        amis_file = self.get_amis_file_path()
        if logger.getEffectiveLevel() <= logging.DEBUG:
            logger.debug(f"Looking up AMI in file: {amis_file}")

        if not os.path.exists(amis_file):
            logger.error(f"AMI file '{amis_file}' not found")
            raise FileNotFoundError(f"AMI file '{amis_file}' not found.")

        try:
            with open(amis_file, mode="r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Region"] == region_name:
                        ami_id = row["AMI ID"]
                        if logger.getEffectiveLevel() <= logging.DEBUG:
                            logger.debug(f"Found AMI for {region_name}: {ami_id}")
                        return ami_id

            logger.error(f"No AMI found for region '{region_name}' in '{amis_file}'")
            raise ValueError(
                f"No AMI found for region '{region_name}' in '{amis_file}'."
            )
        except Exception as e:
            logger.error(f"Error reading AMI file: {str(e)}", exc_info=True)
            raise

    def get_orchestrators(self):
        return self.get("orchestrators", [])

    def get_token(self):
        return self.get("token")

    def get_tls(self):
        return self.get("tls", False)

    def get_public_ssh_key_path(self):
        path = self.get("public_ssh_key_path", "")
        return os.path.expanduser(path) if path else ""

    def get_private_ssh_key_path(self):
        path = self.get("private_ssh_key_path", "")
        return os.path.expanduser(path) if path else ""

    def get_username(self):
        return self.get("username", "bacalhau-runner")
