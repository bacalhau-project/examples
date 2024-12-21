import pytest
import os
import docker
import tempfile
from pathlib import Path

def test_container_orchestrator_connection(docker_client, orchestrator_config):
    # Start orchestrator container
    orchestrator = docker_client.containers.run(
        "bacalhauproject/bacalhau-minimal",
        detach=True,
        environment={
            "BACALHAU_NODE_ID": "test-orchestrator",
            "BACALHAU_API_PORT": "1234"
        },
        volumes={
            orchestrator_config: {
                'bind': '/root/bacalhau-cloud-config.yaml',
                'mode': 'ro'
            }
        },
        network_mode="host"
    )

    try:
        # Start compute container
        compute = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            detach=True,
            environment={
                "BACALHAU_NODE_ID": "test-compute",
                "BACALHAU_NODE_TYPE": "compute",
                "BACALHAU_NODE_NETWORK_ORCHESTRATORS": "localhost:1234"
            },
            network_mode="host"
        )

        # Verify connection
        compute_logs = compute.logs().decode()
        assert "Connected to orchestrator" in compute_logs

    finally:
        # Cleanup
        orchestrator.remove(force=True)
        compute.remove(force=True)

def test_platform_specific_volume_mounts(docker_client):
    test_dir = tempfile.mkdtemp()
    test_file = Path(test_dir) / "test.txt"
    test_file.write_text("test content")

    # Test volume mounting
    container = docker_client.containers.run(
        "bacalhauproject/bacalhau-minimal",
        command=["cat", "/data/test.txt"],
        volumes={
            test_dir: {
                'bind': '/data',
                'mode': 'ro'
            }
        },
        remove=True
    )

    assert container.decode().strip() == "test content"
