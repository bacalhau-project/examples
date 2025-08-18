#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1.7",
#     "semver>=3.0.2",
#     "pyyaml>=6.0.2",
#     "rich>=13.7.0",
# ]
# ///

"""
Docker multi-platform build and push script with semantic versioning.
Replaces the bash build.sh script with Python implementation.
"""

import os
import sys
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import click
import semver
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

class BuildError(Exception):
    """Custom exception for build errors"""
    pass

class DockerBuilder:
    def __init__(
        self,
        image_name: Optional[str] = None,
        platforms: str = "linux/amd64,linux/arm64",
        dockerfile: str = "Dockerfile",
        registry: str = "ghcr.io",
        builder_name: str = "multiarch-builder",
        skip_push: bool = False,
        build_cache: bool = True,
        require_login: bool = True,
    ):
        self.image_name = image_name or self._get_default_image_name()
        self.platforms = platforms
        self.dockerfile = dockerfile
        self.registry = registry
        self.builder_name = builder_name
        self.skip_push = skip_push
        self.build_cache = build_cache
        self.require_login = require_login
        self.github_user = os.environ.get("GITHUB_USER") or self._get_git_user()
        self.github_token = os.environ.get("GITHUB_TOKEN")
        
    def _get_default_image_name(self) -> str:
        """Get image name from current directory"""
        current_dir = Path.cwd().name
        return f"bacalhau-project/{current_dir}"
    
    def _get_git_user(self) -> str:
        """Get git username"""
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "GITHUB_USER_NOT_SET"
    
    def _run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a command and return the result"""
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    
    def validate_requirements(self):
        """Validate all requirements are met"""
        console.print("[blue]Validating requirements...[/blue]")
        
        # Check for required commands
        for cmd, msg in [
            ("docker", "Docker is required but not installed"),
            ("git", "Git is required but not installed"),
        ]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                raise BuildError(msg)
        
        # Check dockerfile exists
        if not Path(self.dockerfile).exists():
            raise BuildError(f"Dockerfile not found at {self.dockerfile}")
        
        # Check docker daemon is running
        result = self._run_command(["docker", "info"], check=False)
        if result.returncode != 0:
            raise BuildError("Docker daemon is not running")
        
        # Check buildx support
        result = self._run_command(["docker", "buildx", "version"], check=False)
        if result.returncode != 0:
            raise BuildError(
                "Docker buildx support is required. Please ensure:\n"
                "1. Docker Desktop is installed and running\n"
                "2. Enable experimental features in Docker settings\n"
                "3. Restart Docker Desktop"
            )
        
        console.print("[green]✓[/green] All requirements validated")
    
    def check_docker_login(self):
        """Check and perform Docker registry login"""
        if not self.require_login or self.skip_push:
            return
        
        console.print("[blue]Checking Docker registry login...[/blue]")
        
        if not self.github_token:
            raise BuildError("GITHUB_TOKEN is not set")
        if not self.github_user:
            raise BuildError("GITHUB_USER is not set")
        
        # Login to registry
        result = subprocess.run(
            ["docker", "login", self.registry, "--username", self.github_user, "--password-stdin"],
            input=self.github_token,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            raise BuildError(f"Failed to log in to Docker registry: {result.stderr}")
        
        console.print("[green]✓[/green] Successfully logged in to Docker registry")
    
    def setup_builder(self):
        """Setup buildx builder"""
        console.print("[blue]Setting up buildx builder...[/blue]")
        
        # Check if builder exists
        result = self._run_command(
            ["docker", "buildx", "inspect", self.builder_name],
            check=False
        )
        
        if result.returncode == 0:
            # Check if builder is running
            result = self._run_command(
                ["docker", "buildx", "inspect", "--bootstrap", self.builder_name],
                check=False
            )
            if "Status: running" in result.stdout:
                console.print(f"[green]✓[/green] Using existing builder '{self.builder_name}'")
                self._run_command(["docker", "buildx", "use", self.builder_name])
                return
            else:
                console.print(f"[yellow]![/yellow] Removing non-functional builder")
                self._run_command(["docker", "buildx", "rm", self.builder_name], check=False)
        
        # Create new builder
        console.print(f"Creating new builder '{self.builder_name}'...")
        self._run_command([
            "docker", "buildx", "create",
            "--name", self.builder_name,
            "--driver", "docker-container",
            "--bootstrap"
        ])
        self._run_command(["docker", "buildx", "use", self.builder_name])
        console.print("[green]✓[/green] Builder created and ready")
    
    def get_current_version(self) -> Optional[semver.Version]:
        """Get the current version from git tags"""
        try:
            result = self._run_command(
                ["git", "tag", "--list", "v*"],
                check=False
            )
            if result.returncode == 0 and result.stdout:
                tags = result.stdout.strip().split('\n')
                # Filter valid semver tags
                versions = []
                for tag in tags:
                    tag = tag.strip()
                    if tag.startswith('v'):
                        tag = tag[1:]
                    try:
                        versions.append(semver.Version.parse(tag))
                    except:
                        continue
                
                if versions:
                    return max(versions)
        except:
            pass
        return None
    
    def bump_version(self, current: Optional[semver.Version], bump_type: str) -> semver.Version:
        """Bump the version based on type"""
        if current is None:
            # Start with 1.0.0 if no version exists
            return semver.Version(1, 0, 0)
        
        if bump_type == "major":
            return current.bump_major()
        elif bump_type == "minor":
            return current.bump_minor()
        elif bump_type == "patch":
            return current.bump_patch()
        else:
            raise BuildError(f"Invalid bump type: {bump_type}")
    
    def parse_version(self, version_str: str) -> semver.Version:
        """Parse and validate a version string"""
        try:
            # Remove 'v' prefix if present
            if version_str.startswith('v'):
                version_str = version_str[1:]
            return semver.Version.parse(version_str)
        except ValueError as e:
            raise BuildError(f"Invalid semver format '{version_str}': {e}")
    
    def create_git_tag(self, version: semver.Version):
        """Create a git tag for the version"""
        tag = f"v{version}"
        console.print(f"[blue]Creating git tag {tag}...[/blue]")
        
        # Check if tag already exists
        result = self._run_command(
            ["git", "tag", "--list", tag],
            check=False
        )
        
        if result.stdout.strip():
            console.print(f"[yellow]![/yellow] Tag {tag} already exists, skipping")
            return
        
        # Create the tag
        self._run_command(["git", "tag", tag])
        console.print(f"[green]✓[/green] Created git tag {tag}")
        
        # Push the tag if not skipping push
        if not self.skip_push:
            console.print(f"[blue]Pushing tag {tag} to remote...[/blue]")
            self._run_command(["git", "push", "origin", tag])
            console.print(f"[green]✓[/green] Pushed tag to remote")
    
    def build_and_push(self, version: semver.Version, datetime_tag: str):
        """Build and push the Docker images"""
        base_tag = f"{self.registry}/{self.image_name}"
        
        # Prepare tags
        tags = [
            f"{base_tag}:latest",
            f"{base_tag}:{datetime_tag}",
            f"{base_tag}:{version}",
            f"{base_tag}:v{version}",
        ]
        
        # Add git commit hash if in git repo
        try:
            result = self._run_command(["git", "rev-parse", "--short", "HEAD"], check=False)
            if result.returncode == 0:
                git_hash = result.stdout.strip()
                tags.append(f"{base_tag}:{git_hash}")
        except:
            pass
        
        # Build command
        build_cmd = [
            "docker", "buildx", "build",
            "--platform", self.platforms,
            "--file", self.dockerfile,
        ]
        
        # Add tags
        for tag in tags:
            build_cmd.extend(["--tag", tag])
        
        # Add cache settings
        if self.build_cache:
            build_cmd.extend([
                "--cache-from", f"type=registry,ref={base_tag}:buildcache",
                "--cache-to", f"type=registry,ref={base_tag}:buildcache,mode=max",
            ])
        
        # Add push or load flag
        if self.skip_push:
            build_cmd.append("--load")
        else:
            build_cmd.append("--push")
        
        # Add build context
        build_cmd.append(".")
        
        # Execute build
        console.print(f"[blue]Building for platforms: {self.platforms}[/blue]")
        console.print(f"[blue]Tags: {', '.join(tags)}[/blue]")
        
        result = self._run_command(build_cmd, check=False)
        if result.returncode != 0:
            raise BuildError(f"Build failed: {result.stderr}")
        
        console.print("[green]✓[/green] Successfully built and pushed images")
        
        return tags
    
    def write_tag_files(self, version: semver.Version, datetime_tag: str):
        """Write tag information to files"""
        full_image_version = f"{self.registry}/{self.image_name}:{version}"
        full_image_latest = f"{self.registry}/{self.image_name}:latest"
        
        console.print("[blue]Writing tag information to files...[/blue]")
        
        Path(".latest-image-tag").write_text(f"{datetime_tag}\n")
        Path(".latest-registry-image").write_text(f"{full_image_version}\n")
        Path(".latest-registry-image-latest").write_text(f"{full_image_latest}\n")
        Path(".latest-semver").write_text(f"{version}\n")
        
        console.print(f"  → .latest-image-tag: {datetime_tag}")
        console.print(f"  → .latest-registry-image: {full_image_version}")
        console.print(f"  → .latest-registry-image-latest: {full_image_latest}")
        console.print(f"  → .latest-semver: {version}")
    
    def print_summary(self, version: semver.Version, datetime_tag: str, tags: List[str]):
        """Print build summary"""
        table = Table(title="Build Summary", show_header=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Image Name", self.image_name)
        table.add_row("Registry", self.registry)
        table.add_row("Semantic Version", str(version))
        table.add_row("DateTime Tag", datetime_tag)
        table.add_row("Platforms", self.platforms)
        table.add_row("Push Status", "Skipped" if self.skip_push else "Pushed")
        
        console.print(table)
        
        if not self.skip_push:
            console.print("\n[green]Ready to run! Copy and paste this command:[/green]\n")
            
            console.print("[dim]# Run the sensor locally:[/dim]")
            run_cmd = f"""docker run --rm \\
  --name sensor-log-generator \\
  -v "$(pwd)/data":/app/data \\
  -v "$(pwd)/config":/app/config \\
  -e CONFIG_FILE=/app/config/config.yaml \\
  -e IDENTITY_FILE=/app/config/identity.json \\
  {self.registry}/{self.image_name}:latest"""
            console.print(run_cmd)
            
            console.print("\n[dim]# Or with custom sensor ID and location:[/dim]")
            custom_cmd = f"""docker run --rm \\
  --name sensor-log-generator \\
  -v "$(pwd)/data":/app/data \\
  -e SENSOR_ID=CUSTOM001 \\
  -e SENSOR_LOCATION="Custom Location" \\
  {self.registry}/{self.image_name}:latest"""
            console.print(custom_cmd)
    
    def cleanup(self):
        """Cleanup builder if needed"""
        try:
            if hasattr(self, 'builder_name'):
                subprocess.run(
                    ["docker", "buildx", "rm", self.builder_name],
                    capture_output=True,
                    check=False
                )
        except:
            pass

@click.command()
@click.option('--image-name', envvar='IMAGE_NAME', help='Docker image name')
@click.option('--platforms', envvar='PLATFORMS', default='linux/amd64,linux/arm64', 
              help='Target platforms')
@click.option('--dockerfile', envvar='DOCKERFILE', default='Dockerfile',
              help='Path to Dockerfile')
@click.option('--registry', envvar='REGISTRY', default='ghcr.io',
              help='Docker registry')
@click.option('--version-tag', envvar='VERSION_TAG',
              help='Explicit version to use (e.g., 1.2.3)')
@click.option('--version-bump', envvar='VERSION_BUMP', 
              type=click.Choice(['major', 'minor', 'patch']),
              default='minor', help='Version bump type')
@click.option('--skip-push/--push', envvar='SKIP_PUSH', default=False,
              help='Skip pushing to registry')
@click.option('--no-cache', 'no_cache', envvar='NO_CACHE', is_flag=True,
              help='Disable build cache')
@click.option('--no-login', 'no_login', envvar='NO_LOGIN', is_flag=True,
              help='Skip Docker registry login')
@click.option('--builder-name', envvar='BUILDER_NAME', default='multiarch-builder',
              help='Buildx builder name')
def main(
    image_name: Optional[str],
    platforms: str,
    dockerfile: str,
    registry: str,
    version_tag: Optional[str],
    version_bump: str,
    skip_push: bool,
    no_cache: bool,
    no_login: bool,
    builder_name: str,
):
    """
    Build and push multi-platform Docker images with semantic versioning.
    
    This script replaces the bash build.sh with Python implementation,
    adding proper semantic versioning support.
    """
    
    console.print(Panel.fit(
        "[bold blue]Docker Multi-Platform Builder[/bold blue]\n"
        "[dim]with Semantic Versioning[/dim]",
        border_style="blue"
    ))
    
    builder = DockerBuilder(
        image_name=image_name,
        platforms=platforms,
        dockerfile=dockerfile,
        registry=registry,
        builder_name=builder_name,
        skip_push=skip_push,
        build_cache=not no_cache,
        require_login=not no_login,
    )
    
    try:
        # Validate requirements
        builder.validate_requirements()
        
        # Check Docker login if needed
        if not skip_push:
            builder.check_docker_login()
        
        # Setup builder
        builder.setup_builder()
        
        # Determine version
        if version_tag:
            # Use explicit version
            version = builder.parse_version(version_tag)
            console.print(f"[blue]Using explicit version: {version}[/blue]")
        else:
            # Get current version and bump
            current_version = builder.get_current_version()
            if current_version:
                console.print(f"[blue]Current version: {current_version}[/blue]")
            else:
                console.print("[blue]No existing version found, starting at 1.0.0[/blue]")
            
            version = builder.bump_version(current_version, version_bump)
            console.print(f"[blue]New version ({version_bump} bump): {version}[/blue]")
        
        # Generate datetime tag
        datetime_tag = datetime.now().strftime("%y%m%d%H%M")
        
        # Build and push
        tags = builder.build_and_push(version, datetime_tag)
        
        # Create git tag
        if not skip_push:
            builder.create_git_tag(version)
        
        # Write tag files
        builder.write_tag_files(version, datetime_tag)
        
        # Print summary
        builder.print_summary(version, datetime_tag, tags)
        
        console.print("\n[bold green]✓ Build completed successfully![/bold green]")
        
    except BuildError as e:
        console.print(f"\n[bold red]✗ Build failed:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Build cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}")
        sys.exit(1)
    finally:
        builder.cleanup()

if __name__ == "__main__":
    main()
