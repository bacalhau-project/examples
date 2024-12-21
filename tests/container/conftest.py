import pytest
import docker
import os
import tempfile

@pytest.fixture
def docker_client():
    # Handle platform-specific socket paths
    socket_path = '/var/run/docker.sock'
    if os.uname().sysname == 'Darwin':
        socket_path = os.getenv('DOCKER_HOST', socket_path)
    return docker.from_env()

@pytest.fixture
def orchestrator_config():
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write("""
        node_type: orchestrator
        api_port: 1234
        publisher_port: 6001
        """)
        f.flush()
        yield f.name
