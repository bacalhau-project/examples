import base64
import io
import logging
import os
import tarfile

from util.config import Config

# Configure logger
logger = logging.getLogger(__name__)


class ScriptsProvider:
    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    @staticmethod
    def _file_path(*path_parts):
        return os.path.join(os.path.dirname(__file__), "..", "instance", *path_parts)

    def get_script_by_name(self, script_name: str) -> dict | None:
        """Get a script by its name from the scripts directory.

        Args:
            script_name: Name of the script to retrieve

        Returns:
            A dictionary containing the script content and metadata if found, or None if not found.
            Returns None silently if the script doesn't exist.
        """
        if not script_name:
            return None

        script_path = os.path.join(self._file_path("scripts"), script_name)
        try:
            with open(script_path, "r") as f:
                content = f.read()
            return {"name": script_name, "content": content, "path": script_path}
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.debug(f"Error reading script {script_name}: {str(e)}")
            return None

    @staticmethod
    def get_ssh_public_key(file_path):
        """Read and validate a public SSH key from the given file path.

        Args:
            file_path: Path to the public SSH key file

        Returns:
            The SSH public key content as a string
        """
        # Handle empty path
        if not file_path:
            return ""

        # Expand any tilde in file path
        expanded_path = os.path.expanduser(file_path)

        # Read and validate key
        try:
            with open(expanded_path, "r") as file:
                content = file.read().strip()

            # Basic validation - public keys should start with ssh-rsa, ssh-ed25519, etc.
            if not (
                content.startswith("ssh-rsa")
                or content.startswith("ssh-ed25519")
                or content.startswith("ssh-dss")
                or content.startswith("ecdsa-sha2")
            ):
                raise ValueError(f"Invalid SSH public key format in {file_path}")

            return content

        except FileNotFoundError:
            print(f"Warning: SSH public key file not found at {expanded_path}")
            return ""
        except Exception as e:
            print(f"Error reading SSH public key: {str(e)}")
            return ""

    @staticmethod
    def encode_file_to_base64(file_path):
        with open(file_path, "rb") as file:
            encoded_content = base64.b64encode(file.read()).decode("utf-8")
        return encoded_content

    def create_bacalhau_config(self):
        values = {
            "bacalhau_token": self.config.get_token(),
            "tls": "true" if self.config.get_tls() else "false",
        }
        with open(self._file_path("config", "config-template.yaml"), "r") as file:
            bacalhau_config = file.read()

        for key, value in values.items():
            bacalhau_config = bacalhau_config.replace(f"${{{key}}}", value)

        bacalhau_config = bacalhau_config.replace(
            "${orchestrators_list}", "\n    - ".join(self.config.get_orchestrators())
        )
        return base64.b64encode(bacalhau_config.encode()).decode("utf-8")

    def tar_and_encode_scripts(self):
        memory_file = io.BytesIO()
        script_dir = self._file_path("scripts")
        with tarfile.open(fileobj=memory_file, mode="w:gz") as tar:
            for script_file in sorted(os.listdir(script_dir)):
                script_path = os.path.join(script_dir, script_file)
                tar.add(script_path, arcname=script_file)

        memory_file.seek(0)
        return base64.b64encode(memory_file.getvalue()).decode()

    def create_cloud_init_script(self):
        # Get public SSH key - handle properly without base64 encoding
        ssh_public_key = self.get_ssh_public_key(self.config.get_public_ssh_key_path())

        values = {
            "compressed_scripts": self.tar_and_encode_scripts(),
            "username": self.config.get_username(),
            "public_ssh_key": ssh_public_key,
            "bacalhau_data_dir": "/bacalhau_data",
            "bacalhau_node_dir": "/bacalhau_node",
            "bacalhau_config_file": self.create_bacalhau_config(),
        }

        with open(self._file_path("cloud-init", "init-vm-template.yml"), "r") as file:
            cloud_init_script = file.read()

        for key, value in values.items():
            cloud_init_script = cloud_init_script.replace(f"${{{key}}}", value)

        return cloud_init_script
