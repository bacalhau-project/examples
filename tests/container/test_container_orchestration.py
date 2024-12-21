import pytest
import os
import docker
import tempfile
from pathlib import Path
import time

def test_container_orchestrator_connection(docker_client, container_mounts):
    """Test container orchestrator connection with configuration."""
    print("\nVerifying config file mount...")
    try:
        # First verify config file is accessible without starting service
        config_check = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            command=["ls", "-l", "/root/bacalhau-cloud-config.yaml"],
            mounts=container_mounts,
            remove=True
        )
        print(f"Config file status:\n{config_check.decode()}")
    except docker.errors.ContainerError as e:
        pytest.fail(f"Failed to access config file: {str(e)}")

    print("\nStarting orchestrator container...")
    # Start orchestrator container
    orchestrator = docker_client.containers.run(
        "bacalhauproject/bacalhau-minimal",
        detach=True,
        environment={
            "BACALHAU_NODE_ID": "test-orchestrator",
            "BACALHAU_NODE_TYPE": "orchestrator",
            "BACALHAU_API_PORT": "1234",
            "BACALHAU_HOST_NETWORK": "true"
        },
        mounts=container_mounts,
        network_mode="host"
    )

    try:
        print("Orchestrator container started, waiting for initialization...")
        print(f"Orchestrator logs: {orchestrator.logs().decode()}")
        # Wait for orchestrator to start (reduced from 5s to 2s)
        time.sleep(2)

        # Start compute container
        print("\nStarting compute container...")
        compute = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            detach=True,
            environment={
                "BACALHAU_NODE_ID": "test-compute",
                "BACALHAU_NODE_TYPE": "compute",
                "BACALHAU_HOST_NETWORK": "true",
                "BACALHAU_DOCKER_HOST": "unix:///var/run/docker.sock",
                "BACALHAU_NODE_NETWORK_ORCHESTRATORS": "localhost:1234"
            },
            mounts=container_mounts,
            network_mode="host"
        )
        print("Compute container started, checking for connection...")

        # Reduced max retries and retry interval for faster failure
        max_retries = 6  # Reduced from 12
        retry_interval = 2  # Reduced from 5
        connected = False

        for _ in range(max_retries):
            compute_logs = compute.logs().decode()
            if "Connected to orchestrator" in compute_logs:
                connected = True
                break
            time.sleep(retry_interval)

        assert connected, f"Connection failed after {max_retries * retry_interval} seconds. Logs: {compute_logs}"

    finally:
        # Cleanup
        orchestrator.remove(force=True)
        compute.remove(force=True)

def test_platform_specific_volume_mounts(docker_client, temp_dir, container_mounts):
    """Test platform-specific volume mounts including config."""
    # First verify config mount
    print("\nVerifying config file mount...")
    try:
        config_check = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            command=["ls", "-l", "/root/bacalhau-cloud-config.yaml"],
            mounts=container_mounts,
            remove=True
        )
        print(f"Config file status:\n{config_check.decode()}")
    except docker.errors.ContainerError as e:
        pytest.fail(f"Failed to access config file: {str(e)}")

    # Test data volume mount
    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("test content")

    try:
        container = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            command=["cat", "/data/test.txt"],
            mounts=container_mounts,
            remove=True,
            timeout=10
        )

        output = container.decode('utf-8').strip()
        assert output == "test content", f"Expected 'test content', got '{output}'"

    except docker.errors.ContainerError as e:
        pytest.fail(f"Container failed: {str(e)}\nMounts: {container_mounts}")
