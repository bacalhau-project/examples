import yaml
import os


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

    def get_image_for_region(self, region_name):
        region_config = self.get_region_config(region_name)
        if not region_config:
            raise ValueError(f"Region '{region_name}' not found in config.")

        image_value = region_config.get("image")
        if image_value != "auto":
            return image_value

        return 'projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20250228'

    def get_orchestrators(self):
        return self.get("orchestrators", [])

    def get_token(self):
        return self.get("token")

    def get_tls(self):
        return self.get("tls", False)

    def get_public_ssh_key_path(self):
        path = self.get("public_ssh_key_path", "")
        return os.path.expanduser(path) if path else ""

    def get_username(self):
        return self.get("username", "bacalhau-runner")
