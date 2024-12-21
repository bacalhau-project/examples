import os
import pytest
import docker
import tempfile
import shutil

@pytest.fixture(scope="session")
def docker_client():
    """Create a Docker client based on the platform."""
    if os.uname().sysname == "Darwin":
        # Use DOCKER_HOST if set on macOS
        docker_host = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        return docker.DockerClient(base_url=docker_host)
    else:
        # Default socket path for Linux
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
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "test_config.yaml"))

@pytest.fixture(scope="function")
def container_mounts(config_file, temp_dir=None):
    """Create container volume mounts including config."""
    mounts = {
        config_file: {
            "bind": "/root/bacalhau-cloud-config.yaml",
            "mode": "ro"
        }
    }

    if temp_dir:
        mounts[temp_dir] = {
            "bind": "/data",
            "mode": "ro"
        }

    return mounts
