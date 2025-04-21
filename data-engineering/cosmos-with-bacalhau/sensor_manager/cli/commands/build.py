"""
Build command implementation.

This module implements the 'build' command for the Sensor Manager CLI,
which builds the CosmosUploader image with versioning.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from sensor_manager.utils import logging as log


def backup_entrypoint():
    """
    Create a backup of the entrypoint.sh file if it doesn't exist.

    Returns:
        bool: True if backup was created or already exists, False on error
    """
    entrypoint_path = Path("cosmos-uploader/entrypoint.sh")
    backup_path = Path("cosmos-uploader/entrypoint.sh.original")

    if not entrypoint_path.exists():
        log.error(f"Entrypoint file not found at {entrypoint_path}")
        return False

    if not backup_path.exists():
        try:
            log.info("Creating backup of entrypoint.sh")
            import shutil

            shutil.copy2(entrypoint_path, backup_path)
            log.success("Backup created")
            return True
        except Exception as e:
            log.error(f"Failed to create backup: {e}")
            return False

    return True


def update_docker_compose(tag):
    """
    Update docker-compose.yml to use the tagged version of the image.

    Args:
        tag: Tag to use for the image

    Returns:
        bool: True if successful, False otherwise
    """
    compose_path = Path("docker-compose.yml")

    if not compose_path.exists():
        log.info("No docker-compose.yml file found to update")
        return True

    try:
        # Read the compose file
        with open(compose_path, "r") as f:
            content = f.read()

        # Replace the image tag
        import re

        updated_content = re.sub(
            r"cosmos-uploader:.*", f"cosmos-uploader:{tag}", content
        )

        # Write back the updated content
        with open(compose_path, "w") as f:
            f.write(updated_content)

        log.success(
            f"Updated docker-compose.yml to use tagged image: cosmos-uploader:{tag}"
        )
        return True
    except Exception as e:
        log.error(f"Failed to update docker-compose.yml: {e}")
        return False


def build_command(args):
    """
    Implementation of the 'build' command.

    Args:
        args: Command-line arguments

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Building CosmosUploader image")

    # Process command-line arguments
    tag = args.tag if hasattr(args, "tag") and args.tag else None
    no_tag = args.no_tag if hasattr(args, "no_tag") else False

    # Generate tag if not provided and not explicitly disabled
    if not tag and not no_tag:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tag = f"v{timestamp}"
        log.info(f"Generated tag: {tag}")

    if not no_tag:
        log.info(f"Using tag: {tag}")

    # Create a backup of the entrypoint.sh file if it doesn't exist
    if not backup_entrypoint():
        log.warning("Continuing without backup of entrypoint.sh")

    # Build the image
    try:
        # Change to the cosmos-uploader directory
        original_dir = os.getcwd()
        os.chdir("cosmos-uploader")

        # Build with or without tag
        if no_tag:
            log.info("Building image without tag")
            result = subprocess.run(
                ["./build.sh", "--push"],  # Always push to registry
                check=True,
                capture_output=True,
                text=True,
            )
            log.success("Build completed: cosmos-uploader:latest")
        else:
            log.info(f"Building image with tag: {tag}")
            result = subprocess.run(
                ["./build.sh", "--tag", tag, "--push"],  # Always push to registry
                check=True,
                capture_output=True,
                text=True,
            )

            # Tag as latest if successful
            if result.returncode == 0:
                subprocess.run(
                    [
                        "docker",
                        "tag",
                        f"cosmos-uploader:{tag}",
                        "cosmos-uploader:latest",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.success(f"Build completed and tagged as:")
                log.info(f"  - cosmos-uploader:{tag}")
                log.info(f"  - cosmos-uploader:latest")

        # Return to original directory
        os.chdir(original_dir)

        # Update docker-compose.yml to use the tagged version if applicable
        if not no_tag:
            update_docker_compose(tag)

        return 0

    except subprocess.CalledProcessError as e:
        log.error(f"Build failed: {e}")
        log.error(f"Error output: {e.stderr}")
        # Return to original directory on error
        if os.getcwd() != original_dir:
            os.chdir(original_dir)
        return 1
    except Exception as e:
        log.error(f"Build failed: {e}")
        # Return to original directory on error
        if os.getcwd() != original_dir:
            os.chdir(original_dir)
        return 1
