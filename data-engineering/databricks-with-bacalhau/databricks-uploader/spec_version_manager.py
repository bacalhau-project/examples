#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "requests>=2.31.0",
#     "pydantic>=2.0.0",
#     "pyyaml>=6.0",
#     "semantic-version>=2.10.0",
#     "click>=8.0.0",
#     "rich>=13.0.0"
# ]
# ///

"""
Schema Version Manager

Manages fetching, caching, and versioning of JSON schemas for data validation.
Supports both S3 and HTTP URLs with local caching and automatic retry logic.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse

import boto3
import requests
import yaml
import click
import shutil
import semantic_version
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


class SchemaMetadata(BaseModel):
    """Metadata about a cached schema."""

    url: str = Field(..., description="Source URL of the schema")
    version: str = Field(..., description="Schema version")
    fetched_at: datetime = Field(..., description="When schema was fetched")
    checksum: str = Field(..., description="SHA256 checksum of schema")
    ttl_hours: int = Field(default=24, description="Cache TTL in hours")

    def is_expired(self) -> bool:
        """Check if cached schema has expired."""
        expiry = self.fetched_at + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry


class JsonSchemaManager:
    """
    Manages JSON Schema fetching, caching, and versioning.

    Features:
    - Fetches schemas from S3 or HTTP URLs
    - Local file caching with TTL
    - Version tracking and validation
    - Automatic retry with exponential backoff
    """

    def __init__(
        self,
        cache_dir: str = "/tmp/schema_cache",
        default_ttl_hours: int = 24,
        max_retries: int = 3,
        aws_region: str = "us-west-2",
    ):
        """
        Initialize the schema manager.

        Args:
            cache_dir: Directory for caching schemas
            default_ttl_hours: Default cache TTL in hours
            max_retries: Maximum number of fetch retries
            aws_region: AWS region for S3 access
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl_hours = default_ttl_hours
        self.max_retries = max_retries
        self.aws_region = aws_region

        # Initialize S3 client lazily
        self._s3_client = None

        # In-memory cache for current session
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.aws_region)
        return self._s3_client

    def get_cache_path(self, url: str, version: str) -> Path:
        """Get local cache file path for a schema."""
        parsed = urlparse(url)
        safe_name = f"{parsed.netloc}_{parsed.path.replace('/', '_')}"
        safe_name = safe_name.replace(".", "_")
        return self.cache_dir / f"{safe_name}_{version}.json"

    def get_metadata_path(self, url: str, version: str) -> Path:
        """Get path to metadata file for cached schema."""
        cache_path = self.get_cache_path(url, version)
        return cache_path.with_suffix(".meta.json")

    def fetch_from_s3(self, url: str) -> Dict[str, Any]:
        """Fetch schema from S3 URL."""
        parsed = urlparse(url)

        if parsed.scheme == "s3":
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
        elif "s3" in parsed.netloc and "amazonaws.com" in parsed.netloc:
            parts = parsed.netloc.split(".")
            bucket = parts[0]
            key = parsed.path.lstrip("/")
        else:
            raise ValueError(f"Invalid S3 URL format: {url}")

        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch schema from S3: {e}")

    def fetch_from_http(self, url: str) -> Dict[str, Any]:
        """Fetch schema from HTTP/HTTPS URL."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch schema from HTTP: {e}")

    def fetch_schema(self, url: str) -> Dict[str, Any]:
        """Fetch schema from URL with retry logic."""
        parsed = urlparse(url)

        for attempt in range(self.max_retries):
            try:
                if parsed.scheme in ("s3",) or "s3.amazonaws.com" in url:
                    return self.fetch_from_s3(url)
                elif parsed.scheme in ("http", "https"):
                    return self.fetch_from_http(url)
                else:
                    raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise

                wait_time = 2**attempt
                print(f"Fetch attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)

        raise RuntimeError(f"Failed to fetch schema after {self.max_retries} attempts")

    def calculate_checksum(self, schema: Dict[str, Any]) -> str:
        """Calculate SHA256 checksum of schema."""
        import hashlib

        schema_str = json.dumps(schema, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()

    def save_to_cache(
        self, url: str, version: str, schema: Dict[str, Any], ttl_hours: Optional[int] = None
    ) -> None:
        """Save schema to local cache."""
        cache_path = self.get_cache_path(url, version)
        metadata_path = self.get_metadata_path(url, version)

        with open(cache_path, "w") as f:
            json.dump(schema, f, indent=2)

        metadata = SchemaMetadata(
            url=url,
            version=version,
            fetched_at=datetime.now(),
            checksum=self.calculate_checksum(schema),
            ttl_hours=ttl_hours or self.default_ttl_hours,
        )

        with open(metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))

        cache_key = f"{url}:{version}"
        self._memory_cache[cache_key] = schema

    def load_from_cache(self, url: str, version: str) -> Optional[Dict[str, Any]]:
        """Load schema from cache if valid."""
        cache_key = f"{url}:{version}"
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        cache_path = self.get_cache_path(url, version)
        metadata_path = self.get_metadata_path(url, version)

        if not cache_path.exists() or not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                metadata = SchemaMetadata.model_validate_json(f.read())

            if metadata.is_expired():
                print(f"Cache expired for {url} version {version}")
                return None

            with open(cache_path, "r") as f:
                schema = json.load(f)

            if self.calculate_checksum(schema) != metadata.checksum:
                print(f"Checksum mismatch for cached schema {url} version {version}")
                return None

            self._memory_cache[cache_key] = schema
            return schema

        except Exception as e:
            print(f"Error loading cached schema: {e}")
            return None

    def get_schema(
        self,
        url: str,
        version: str = "latest",
        force_refresh: bool = False,
        ttl_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get schema with caching."""
        if not force_refresh:
            cached = self.load_from_cache(url, version)
            if cached:
                print(f"Using cached schema for {url} version {version}")
                return cached

        print(f"Fetching schema from {url}")
        schema = self.fetch_schema(url)

        if version == "latest" and "$id" in schema:
            schema_id = schema.get("$id", "")
            if "v" in schema_id:
                version = schema_id.split("v")[-1].split("/")[0]

        self.save_to_cache(url, version, schema, ttl_hours)
        return schema


class SpecVersionManager:
    """Manages validation specification versions."""

    def __init__(self, specs_dir: str = "specs"):
        self.specs_dir = Path(specs_dir)
        self.specs_dir.mkdir(exist_ok=True)
        self.current_link = self.specs_dir / "current"

    def get_current_version(self) -> Optional[str]:
        """Get the current spec version."""
        if self.current_link.exists():
            current_spec = self.current_link / "sensor_validation_spec.yaml"
            if current_spec.exists():
                with open(current_spec) as f:
                    spec = yaml.safe_load(f)
                    return spec.get("version")
        return None

    def create_version(self, version: str, author: str, changelog: str):
        """Create a new version of the specification."""
        # Validate version format
        try:
            semver = semantic_version.Version(version)
        except ValueError:
            raise ValueError(f"Invalid version format: {version}")

        # Create version directory
        version_dir = self.specs_dir / f"v{version}"
        if version_dir.exists():
            raise ValueError(f"Version {version} already exists")
        version_dir.mkdir(exist_ok=True)

        # Copy current spec or create new
        new_spec_path = version_dir / "sensor_validation_spec.yaml"

        if self.current_link.exists():
            current_spec_path = self.current_link / "sensor_validation_spec.yaml"
            if current_spec_path.exists():
                # Load current spec
                with open(current_spec_path) as f:
                    spec = yaml.safe_load(f)

                # Check version increment rules
                current_version = semantic_version.Version(spec["version"])
                if semver <= current_version:
                    raise ValueError(
                        f"New version {version} must be greater than current {current_version}"
                    )

                # Update version info
                old_version = spec["version"]
                spec["version"] = version
                spec["last_modified"] = datetime.now(timezone.utc).isoformat()
                spec["author"] = author

                # Add to version history
                if "version_history" not in spec:
                    spec["version_history"] = []
                spec["version_history"].append(
                    {
                        "version": old_version,
                        "date": spec.get("last_modified", "unknown"),
                        "author": spec.get("author", "unknown"),
                    }
                )

                # Keep only last 10 versions in history
                spec["version_history"] = spec["version_history"][-10:]
            else:
                # Create from current sensor_validation_spec.yaml if it exists
                default_spec_path = Path("sensor_validation_spec.yaml")
                if default_spec_path.exists():
                    with open(default_spec_path) as f:
                        spec = yaml.safe_load(f)
                    spec["version"] = version
                    spec["last_modified"] = datetime.now(timezone.utc).isoformat()
                    spec["author"] = author
                else:
                    spec = self._create_template_spec(version, author)
        else:
            # First version - check if sensor_validation_spec.yaml exists
            default_spec_path = Path("sensor_validation_spec.yaml")
            if default_spec_path.exists():
                with open(default_spec_path) as f:
                    spec = yaml.safe_load(f)
                spec["version"] = version
                spec["last_modified"] = datetime.now(timezone.utc).isoformat()
                spec["author"] = author
            else:
                spec = self._create_template_spec(version, author)

        # Save new spec
        with open(new_spec_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, width=120)

        # Create changelog
        changelog_file = version_dir / "CHANGELOG.md"
        with open(changelog_file, "w") as f:
            f.write(f"# Changelog for Version {version}\n\n")
            f.write(f"**Date**: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"**Author**: {author}\n\n")
            f.write("## Changes\n\n")
            f.write(changelog)

        # Update current symlink
        if self.current_link.exists():
            if self.current_link.is_symlink():
                self.current_link.unlink()
            else:
                shutil.rmtree(self.current_link)

        # Create relative symlink
        self.current_link.symlink_to(version_dir.name)

        return version_dir

    def _create_template_spec(self, version: str, author: str) -> Dict[str, Any]:
        """Create a template specification."""
        return {
            "version": version,
            "name": "Sensor Validation Specification",
            "last_modified": datetime.now(timezone.utc).isoformat(),
            "author": author,
            "compatible_with": {
                "min_version": version,
                "max_version": str(semantic_version.Version(version).next_major()),
            },
            "fields": {
                "sensor_id": {
                    "type": "string",
                    "required": True,
                    "pattern": "^[A-Z]{3}_\\d{3}$",
                    "description": "Sensor identifier",
                },
                "timestamp": {
                    "type": "string",
                    "required": True,
                    "format": "date-time",
                    "description": "ISO 8601 timestamp",
                },
                "temperature": {
                    "type": "float",
                    "required": True,
                    "min": 0.0,
                    "max": 100.0,
                    "unit": "°C",
                    "description": "Temperature reading",
                },
            },
            "version_history": [],
        }

    def list_versions(self) -> List[Dict[str, Any]]:
        """List all available versions."""
        versions = []

        # Get current version if it exists
        current_target = None
        if self.current_link.exists() and self.current_link.is_symlink():
            current_target = self.current_link.resolve().name

        for path in self.specs_dir.iterdir():
            if path.is_dir() and path.name.startswith("v"):
                version = path.name[1:]  # Remove 'v' prefix
                spec_file = path / "sensor_validation_spec.yaml"
                changelog_file = path / "CHANGELOG.md"

                if spec_file.exists():
                    with open(spec_file) as f:
                        spec = yaml.safe_load(f)
                        versions.append(
                            {
                                "version": version,
                                "date": spec.get("last_modified", "unknown"),
                                "author": spec.get("author", "unknown"),
                                "is_current": path.name == current_target,
                                "has_changelog": changelog_file.exists(),
                            }
                        )

        return sorted(versions, key=lambda x: semantic_version.Version(x["version"]), reverse=True)

    def diff_versions(self, version1: str, version2: str) -> Dict[str, Any]:
        """Compare two versions of the specification."""
        spec1 = self._load_version(version1)
        spec2 = self._load_version(version2)

        diff = {
            "version1": version1,
            "version2": version2,
            "fields": {"added": [], "removed": [], "modified": []},
            "rules": {"added": [], "removed": [], "modified": []},
            "thresholds": {"modified": []},
        }

        # Compare fields
        fields1 = set(spec1.get("fields", {}).keys())
        fields2 = set(spec2.get("fields", {}).keys())

        diff["fields"]["added"] = sorted(list(fields2 - fields1))
        diff["fields"]["removed"] = sorted(list(fields1 - fields2))

        # Check for modified fields
        for field in fields1 & fields2:
            field1_spec = spec1["fields"][field]
            field2_spec = spec2["fields"][field]

            if field1_spec != field2_spec:
                changes = []

                # Check specific changes
                for key in set(field1_spec.keys()) | set(field2_spec.keys()):
                    val1 = field1_spec.get(key)
                    val2 = field2_spec.get(key)
                    if val1 != val2:
                        changes.append({"property": key, "old": val1, "new": val2})

                diff["fields"]["modified"].append({"field": field, "changes": changes})

        # Compare cross-field rules
        rules1 = spec1.get("cross_field_rules", [])
        rules2 = spec2.get("cross_field_rules", [])

        # Simple comparison - could be enhanced
        if len(rules1) != len(rules2):
            diff["rules"]["modified"].append(
                {"type": "cross_field_rules", "old_count": len(rules1), "new_count": len(rules2)}
            )

        return diff

    def _load_version(self, version: str) -> Dict[str, Any]:
        """Load a specific version of the specification."""
        spec_file = self.specs_dir / f"v{version}" / "sensor_validation_spec.yaml"
        if not spec_file.exists():
            raise ValueError(f"Version {version} not found")
        with open(spec_file) as f:
            return yaml.safe_load(f)

    def validate_compatibility(self, data_version: str) -> bool:
        """Check if data validated with a specific version is compatible with current."""
        current_version = self.get_current_version()
        if not current_version:
            return False

        current_spec = self._load_version(current_version)

        # Check compatibility range
        compatible_with = current_spec.get("compatible_with", {})
        min_version = semantic_version.Version(compatible_with.get("min_version", "0.0.0"))
        max_version = semantic_version.Version(compatible_with.get("max_version", "999.999.999"))

        try:
            data_semver = semantic_version.Version(data_version)
            return min_version <= data_semver < max_version
        except:
            return False

    def get_changelog(self, version: str) -> Optional[str]:
        """Get changelog for a specific version."""
        changelog_file = self.specs_dir / f"v{version}" / "CHANGELOG.md"
        if changelog_file.exists():
            with open(changelog_file) as f:
                return f.read()
        return None


@click.group()
def cli():
    """Validation Specification Version Manager"""
    pass


@cli.command()
@click.option("--version", required=True, help="New version number (e.g., 1.2.3)")
@click.option("--author", required=True, help="Author email or identifier")
@click.option("--changelog", required=True, help="Description of changes")
def create(version: str, author: str, changelog: str):
    """Create a new version of the specification."""
    manager = SpecVersionManager()

    try:
        version_dir = manager.create_version(version, author, changelog)
        console.print(f"[green]✓[/green] Created version {version} at {version_dir}")
        console.print(f"[green]✓[/green] Updated current symlink to point to v{version}")

        # Show version info
        panel = Panel(
            f"[bold]Version:[/bold] {version}\n"
            f"[bold]Author:[/bold] {author}\n"
            f"[bold]Date:[/bold] {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"[bold]Changelog:[/bold]\n{changelog}",
            title="New Version Created",
            border_style="green",
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise click.Abort()


@cli.command()
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
def list(format: str):
    """List all specification versions."""
    manager = SpecVersionManager()
    versions = manager.list_versions()

    if not versions:
        console.print("[yellow]No versions found[/yellow]")
        return

    if format == "json":
        click.echo(json.dumps(versions, indent=2))
    else:
        table = Table(title="Specification Versions", show_header=True, header_style="bold magenta")
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Date", style="green")
        table.add_column("Author", style="yellow")
        table.add_column("Status", style="white")

        for v in versions:
            status = "[bold green]CURRENT[/bold green]" if v["is_current"] else ""
            if v["has_changelog"]:
                status += " 📝" if not v["is_current"] else " 📝"

            table.add_row(
                f"v{v['version']}",
                v["date"][:10] if v["date"] != "unknown" else v["date"],
                v["author"],
                status,
            )

        console.print(table)


@cli.command()
@click.argument("version1")
@click.argument("version2")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def diff(version1: str, version2: str, format: str):
    """Show differences between two versions."""
    manager = SpecVersionManager()

    try:
        differences = manager.diff_versions(version1, version2)

        if format == "json":
            click.echo(json.dumps(differences, indent=2))
        else:
            console.print(f"\n[bold]Differences between v{version1} and v{version2}:[/bold]")
            console.print("=" * 60)

            # Fields
            if differences["fields"]["added"]:
                console.print("\n[green]Fields Added:[/green]")
                for field in differences["fields"]["added"]:
                    console.print(f"  [green]+[/green] {field}")

            if differences["fields"]["removed"]:
                console.print("\n[red]Fields Removed:[/red]")
                for field in differences["fields"]["removed"]:
                    console.print(f"  [red]-[/red] {field}")

            if differences["fields"]["modified"]:
                console.print("\n[yellow]Fields Modified:[/yellow]")
                for mod in differences["fields"]["modified"]:
                    console.print(f"  [yellow]~[/yellow] {mod['field']}")
                    for change in mod["changes"]:
                        console.print(
                            f"    • {change['property']}: {change['old']} → {change['new']}"
                        )

            # Rules
            if differences["rules"]["modified"]:
                console.print("\n[yellow]Rules Modified:[/yellow]")
                for rule in differences["rules"]["modified"]:
                    console.print(
                        f"  • {rule['type']}: {rule['old_count']} → {rule['new_count']} rules"
                    )

            if not any(
                [
                    differences["fields"]["added"],
                    differences["fields"]["removed"],
                    differences["fields"]["modified"],
                    differences["rules"]["modified"],
                ]
            ):
                console.print("\n[green]No differences found[/green]")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise click.Abort()


@cli.command()
@click.argument("data_version")
def check_compatibility(data_version: str):
    """Check if data from a specific version is compatible with current."""
    manager = SpecVersionManager()
    current = manager.get_current_version()

    if not current:
        console.print("[red]✗ No current version found[/red]")
        return

    if manager.validate_compatibility(data_version):
        console.print(
            f"[green]✓[/green] Data from v{data_version} is compatible with current v{current}"
        )
    else:
        console.print(
            f"[red]✗[/red] Data from v{data_version} is NOT compatible with current v{current}"
        )

        # Show compatibility range
        try:
            current_spec = manager._load_version(current)
            compatible_with = current_spec.get("compatible_with", {})
            console.print(
                f"\n[yellow]Current version v{current} is compatible with:[/yellow]\n"
                f"  Min version: {compatible_with.get('min_version', 'not specified')}\n"
                f"  Max version: {compatible_with.get('max_version', 'not specified')}"
            )
        except:
            pass


@cli.command()
@click.argument("version")
def show_changelog(version: str):
    """Show changelog for a specific version."""
    manager = SpecVersionManager()

    changelog = manager.get_changelog(version)
    if changelog:
        console.print(Panel(changelog, title=f"Changelog for v{version}", border_style="blue"))
    else:
        console.print(f"[yellow]No changelog found for version {version}[/yellow]")


@cli.command()
def current():
    """Show current version information."""
    manager = SpecVersionManager()
    current_version = manager.get_current_version()

    if not current_version:
        console.print("[yellow]No current version set[/yellow]")
        return

    try:
        spec = manager._load_version(current_version)

        # Create info panel
        info = f"""[bold]Version:[/bold] {current_version}
[bold]Name:[/bold] {spec.get("name", "Unknown")}
[bold]Last Modified:[/bold] {spec.get("last_modified", "Unknown")}
[bold]Author:[/bold] {spec.get("author", "Unknown")}

[bold]Compatibility:[/bold]
  Min Version: {spec.get("compatible_with", {}).get("min_version", "Not specified")}
  Max Version: {spec.get("compatible_with", {}).get("max_version", "Not specified")}

[bold]Fields:[/bold] {len(spec.get("fields", {}))} defined
[bold]Rules:[/bold] {len(spec.get("cross_field_rules", []))} cross-field rules
[bold]Routing:[/bold] {len(spec.get("routing_rules", {}))} routing rules"""

        console.print(Panel(info, title="Current Specification", border_style="cyan"))

        # Show recent history
        history = spec.get("version_history", [])
        if history:
            console.print("\n[bold]Recent Version History:[/bold]")
            for entry in history[-5:]:  # Show last 5
                console.print(f"  • v{entry['version']} ({entry.get('date', 'unknown')[:10]})")

    except Exception as e:
        console.print(f"[red]✗ Error loading current version:[/red] {e}")


if __name__ == "__main__":
    cli()
