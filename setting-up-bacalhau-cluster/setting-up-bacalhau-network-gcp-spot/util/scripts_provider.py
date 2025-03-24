import base64
import os

from util.config import Config


class ScriptsProvider:
    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    @staticmethod
    def _file_path(*path_parts):
        return os.path.join(os.path.dirname(__file__), '..', 'instance', *path_parts)

    @staticmethod
    def get_ssh_public_key(file_path):
        with open(file_path, "r") as file:
            content = file.read()
        return content

    @staticmethod
    def encode_file_to_base64(file_path):
        with open(file_path, "rb") as file:
            encoded_content = base64.b64encode(file.read()).decode("utf-8")
        return encoded_content

    def create_bacalhau_config(self):
        values = {
            "bacalhau_token": self.config.get_token(),
            "tls": "true" if self.config.get_tls() else "false"
        }
        with open(self._file_path("config", "config-template.yaml"), "r") as file:
            bacalhau_config = file.read()

        for key, value in values.items():
            bacalhau_config = bacalhau_config.replace(f"${{{key}}}", value)

        bacalhau_config = bacalhau_config.replace("${orchestrators_list}",
                                                  "\n    - ".join(self.config.get_orchestrators()))
        return base64.b64encode(bacalhau_config.encode()).decode("utf-8")

    def create_cloud_init_script(self):
        values = {
            "username": self.config.get_username(),
            "public_ssh_key": base64.b64encode(
                self.get_ssh_public_key(self.config.get_public_ssh_key_path()).encode()).decode("utf-8"),
            "docker_install_script_file": self.encode_file_to_base64(self._file_path("scripts", "install_docker.sh")),
            "bacalhau_data_dir": "/bacalhau_data",
            "bacalhau_node_dir": "/bacalhau_node",
            "bacalhau_startup_service_file": self.encode_file_to_base64(
                self._file_path("scripts", "bacalhau-startup.service")),
            "bacalhau_startup_script_file": self.encode_file_to_base64(self._file_path("scripts", "startup.sh")),
            "bacalhau_config_file": self.create_bacalhau_config(),
            "docker_compose_file": self.encode_file_to_base64(self._file_path("config", "docker-compose.yml")),
            "healthz_web_server_script_file": self.encode_file_to_base64(
                self._file_path("scripts", "healthz-web-server.py")),
            "healthz_service_file": self.encode_file_to_base64(self._file_path("scripts", "healthz-web.service"))
        }

        with open(self._file_path("cloud-init", "init-vm-template.yml"), "r") as file:
            cloud_init_script = file.read()

        for key, value in values.items():
            cloud_init_script = cloud_init_script.replace(f"${{{key}}}", value)

        return cloud_init_script
