"""
Docker Compose functionality for the Sensor Manager.

This module handles the generation and management of Docker Compose configurations
for sensor simulation and data uploading.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from jinja2 import Environment, FileSystemLoader

from sensor_manager.utils import logging as log


class DockerComposeGenerator:
    """Generator for Docker Compose configurations."""

    def __init__(self, output_path: str = "docker-compose.yml"):
        """
        Initialize the Docker Compose generator.

        Args:
            output_path: Path to the output Docker Compose file
        """
        self.output_path = output_path
        self.template_dir = Path(__file__).parent.parent / "templates"

        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_from_template(self, template_name: str, context: Dict) -> bool:
        """
        Generate Docker Compose file from a Jinja2 template.

        Args:
            template_name: Name of the template file
            context: Context data for template rendering

        Returns:
            True if successful, False otherwise
        """
        try:
            template = self.jinja_env.get_template(template_name)
            rendered = template.render(**context)

            with open(self.output_path, "w") as f:
                f.write(rendered)

            log.success(f"Generated Docker Compose file at {self.output_path}")
            return True
        except Exception as e:
            log.error(f"Failed to generate Docker Compose file: {e}")
            return False

    def generate_multi_region(
        self,
        config_file: str,
        sensor_config_file: str,
        sensors_per_city: int = 3,
        readings_per_second: int = 1,
        anomaly_probability: float = 0.05,
        upload_interval: int = 30,
        archive_format: str = "Parquet",
    ) -> bool:
        """
        Generate a multi-region Docker Compose file similar to generate-multi-sensor-compose.sh.

        This is a placeholder implementation that will be extended in future steps.
        Currently, it just demonstrates how the function will work.

        Args:
            config_file: Path to the configuration file
            sensor_config_file: Path to the sensor configuration file
            sensors_per_city: Number of sensors per city
            readings_per_second: Readings per second
            anomaly_probability: Probability of anomalies
            upload_interval: Upload interval in seconds
            archive_format: Format for archived data

        Returns:
            True if successful, False otherwise
        """
        log.info(f"Generating multi-region Docker Compose file at {self.output_path}")
        log.info(f"  - Config file: {config_file}")
        log.info(f"  - Sensor config: {sensor_config_file}")
        log.info(f"  - Sensors per city: {sensors_per_city}")

        # This is a placeholder - in future steps we'll implement the actual generation
        # using Jinja2 templates or direct YAML generation

        return True


class DockerComposeRunner:
    """Runner for Docker Compose operations."""

    def __init__(
        self,
        compose_file: str = "docker-compose.yml",
        project_name: Optional[str] = None,
    ):
        """
        Initialize the Docker Compose runner.

        Args:
            compose_file: Path to the Docker Compose file
            project_name: Project name for Docker Compose
        """
        self.compose_file = compose_file
        self.project_name = project_name

    def _build_cmd(self, *args) -> List[str]:
        """
        Build Docker Compose command with the specified arguments.

        Args:
            *args: Command-line arguments for Docker Compose

        Returns:
            List of command-line arguments
        """
        cmd = ["docker", "compose"]

        if self.project_name:
            cmd.extend(["-p", self.project_name])

        cmd.extend(args)
        return cmd

    def run(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """
        Run a Docker Compose command.

        Args:
            *args: Command-line arguments for Docker Compose
            check: Whether to check the return code

        Returns:
            CompletedProcess instance with the command result
        """
        cmd = self._build_cmd(*args)
        log.debug(f"Running command: {' '.join(cmd)}")

        try:
            return subprocess.run(cmd, check=check, text=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log.error(f"Docker Compose command failed: {e}")
            log.error(f"Error output: {e.stderr}")
            raise

    def up(self, detach: bool = True) -> bool:
        """
        Start containers with Docker Compose.

        Args:
            detach: Whether to run in detached mode

        Returns:
            True if successful, False otherwise
        """
        try:
            args = ["up"]
            if detach:
                args.append("-d")

            result = self.run(*args)
            log.success("Started containers with Docker Compose")
            return True
        except Exception as e:
            log.error(f"Failed to start containers: {e}")
            return False

    def down(self) -> bool:
        """
        Stop and remove containers with Docker Compose.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.run("down")
            log.success("Stopped and removed containers with Docker Compose")
            return True
        except Exception as e:
            log.error(f"Failed to stop containers: {e}")
            return False

    def ps(self) -> str:
        """
        List containers managed by Docker Compose.

        Returns:
            Output of the Docker Compose ps command
        """
        try:
            result = self.run("ps")
            return result.stdout
        except Exception as e:
            log.error(f"Failed to list containers: {e}")
            return ""
