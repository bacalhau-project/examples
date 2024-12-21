import os
import pytest
import docker
import tempfile
import shutil
from pathlib import Path

@pytest.fixture(scope="session")
def docker_client():
    """Create a Docker client."""
    # Use default socket path as we're only supporting Linux now
    return docker.DockerClient(base_url="unix:///var/run/docker.sock")

@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture(scope="function")
def config_file():
    """Get path to the test configuration file."""
    config_path = Path(__file__).parent / "test_config.yaml"
    return str(config_path.resolve())

@pytest.fixture(scope="function")
def container_mounts(config_file, temp_dir=None):
    """Create container volume mounts including config."""
    # Ensure the config file exists
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found at {config_file}")

    mounts = {
        config_file: {
            "bind": "/root/bacalhau-cloud-config.yaml",
            "mode": "ro"
        }
    }

    if temp_dir:
        mounts[temp_dir] = {
            "bind": "/data",
            "mode": "rw"  # Changed to rw to allow tests to write files
        }

    return mounts
