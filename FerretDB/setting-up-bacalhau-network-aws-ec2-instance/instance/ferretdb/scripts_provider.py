import base64
import os

from util.scripts_provider import ScriptsProvider

# SCRIPTS_DIR = "ferret-db-init-scripts"


class FerretdbScriptsProvider(ScriptsProvider):

    def _file_path(self, *path_parts):
        return os.path.join(os.path.dirname(__file__), '.', *path_parts)

    def create_cloud_init_script(self, region_config):
        values = {
            "compressed_scripts": self.tar_and_encode_scripts(),
            "username": self.config.get_username(),
            "public_ssh_key": base64.b64encode(
                self.get_ssh_public_key(self.config.get_public_ssh_key_path()).encode()).decode("utf-8"),
            "additional_env_vars": self.config.get_env_for_region(region_config)
        }

        with open(self._file_path("cloud-init", "init-vm-template.yml"), "r") as file:
            cloud_init_script = file.read()

        for key, value in values.items():
            cloud_init_script = cloud_init_script.replace(f"${{{key}}}", value)

        return cloud_init_script
