import pytest
import os
import docker
import tempfile
from pathlib import Path

def test_container_orchestrator_connection(docker_client, container_mounts):
    # Start orchestrator container
    orchestrator = docker_client.containers.run(
        "bacalhauproject/bacalhau-minimal",
        detach=True,
        environment={
            "BACALHAU_NODE_ID": "test-orchestrator",
            "BACALHAU_API_PORT": "1234"
        },
        volumes=container_mounts,
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

def test_platform_specific_volume_mounts(docker_client, temp_dir, container_mounts):
    test_file = os.path.join(temp_dir, "test.txt")
    test_file.write_text("test content")

    # Test volume mounting
    container = docker_client.containers.run(
        "bacalhauproject/bacalhau-minimal",
        command=["cat", "/data/test.txt"],
        volumes=container_mounts,
        remove=True
    )

    assert "test content" in container.decode('utf-8')
