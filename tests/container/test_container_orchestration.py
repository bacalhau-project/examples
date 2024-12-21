import pytest
import os
import docker
import tempfile
from pathlib import Path
import time

@pytest.mark.timeout(30)
def test_container_orchestrator_connection(docker_client, container_mounts):
    """Test container orchestrator connection with configuration."""
    containers = []
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

    print("\nStarting orchestrator container...")
    try:
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
            network_mode="host",
            privileged=True,
            security_opt=['seccomp=unconfined', 'apparmor=unconfined']
        )
        containers.append(orchestrator)

        print("Orchestrator container started, waiting for initialization...")
        orchestrator_logs = orchestrator.logs().decode()
        print(f"Orchestrator logs: {orchestrator_logs}")

        if "error" in orchestrator_logs.lower():
            pytest.fail(f"Orchestrator failed to start: {orchestrator_logs}")

        if "Started Bacalhau" not in orchestrator_logs:
            time.sleep(1)

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
            network_mode="host",
            privileged=True,
            security_opt=['seccomp=unconfined', 'apparmor=unconfined']
        )
        containers.append(compute)
        print("Compute container started, checking for connection...")

        max_retries = 3
        retry_interval = 1
        connected = False

        for attempt in range(max_retries):
            compute_logs = compute.logs().decode()
            if "error" in compute_logs.lower():
                pytest.fail(f"Compute node error on attempt {attempt + 1}: {compute_logs}")
            if "Connected to orchestrator" in compute_logs:
                connected = True
                break
            print(f"Attempt {attempt + 1}/{max_retries}: Waiting for connection...")
            time.sleep(retry_interval)

        assert connected, f"Connection failed after {max_retries * retry_interval} seconds. Logs: {compute_logs}"

    finally:
        for container in containers:
            try:
                container.remove(force=True)
            except Exception as e:
                print(f"Warning: Failed to remove container: {e}")

@pytest.mark.timeout(15)
def test_platform_specific_volume_mounts(docker_client, temp_dir, container_mounts):
    """Test platform-specific volume mounts including config."""
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

    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("test content")

    try:
        container = docker_client.containers.run(
            "bacalhauproject/bacalhau-minimal",
            command=["cat", "/data/test.txt"],
            mounts=container_mounts,
            remove=True,
            timeout=5
        )

        output = container.decode('utf-8').strip()
        assert output == "test content", f"Expected 'test content', got '{output}'"

    except docker.errors.ContainerError as e:
        pytest.fail(f"Container failed: {str(e)}\nMounts: {container_mounts}")
