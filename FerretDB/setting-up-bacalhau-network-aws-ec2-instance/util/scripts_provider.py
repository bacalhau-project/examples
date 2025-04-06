import base64
import io
import os
import tarfile


class ScriptsProvider:
    def __init__(self, config):
        super().__init__()
        self.config = config

    def _file_path(self, *path_parts):
        return os.path.join(os.path.dirname(__file__), '..', 'instance', 'default', *path_parts)

    @staticmethod
    def get_ssh_public_key(file_path):
        with open(file_path, "r") as file:
            content = file.read()
        return content

    def create_bacalhau_config(self):
        values = {
            "bacalhau_token": self.config.get_token(),
            "tls": "true" if self.config.get_tls() else "false"
        }
        with open(self._file_path("config", "config-template.yaml"), "r", newline="\n") as file:
            bacalhau_config = file.read()

        for key, value in values.items():
            bacalhau_config = bacalhau_config.replace(f"${{{key}}}", value)

        bacalhau_config = bacalhau_config.replace("${orchestrators_list}",
                                                  "\n    - ".join(self.config.get_orchestrators()))
        return base64.b64encode(bacalhau_config.encode()).decode("utf-8")

    def tar_and_encode_scripts(self):
        memory_file = io.BytesIO()
        script_dir = self._file_path("scripts")

        with tarfile.open(fileobj=memory_file, mode="w:gz") as tar:
            for script_file in sorted(os.listdir(script_dir)):
                script_path = os.path.join(script_dir, script_file)

                with open(script_path, 'r', newline='') as f:
                    content = f.read().replace('\r\n', '\n').replace('\r', '\n')

                temp_file = io.BytesIO(content.encode('utf-8'))
                tarinfo = tarfile.TarInfo(name=script_file)
                tarinfo.size = len(temp_file.getvalue())

                tar.addfile(tarinfo, fileobj=temp_file)

        memory_file.seek(0)
        return base64.b64encode(memory_file.getvalue()).decode()

    def create_cloud_init_script(self, region_config):
        values = {
            "compressed_scripts": self.tar_and_encode_scripts(),
            "username": self.config.get_username(),
            "public_ssh_key": base64.b64encode(
                self.get_ssh_public_key(self.config.get_public_ssh_key_path()).encode()).decode("utf-8"),
            "bacalhau_data_dir": "/bacalhau_data",
            "bacalhau_node_dir": "/bacalhau_node",
            "bacalhau_config_file": self.create_bacalhau_config(),
            "additional_env_vars": self.config.get_env_for_region(region_config)
        }

        with open(self._file_path("cloud-init", "init-vm-template.yml"), "r", newline="\n") as file:
            cloud_init_script = file.read()

        for key, value in values.items():
            cloud_init_script = cloud_init_script.replace(f"${{{key}}}", value)

        return cloud_init_script
