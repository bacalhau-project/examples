#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pyyaml",
#     "pydantic",
# ]
# ///

import json
import os
import sys
import tempfile
from pathlib import Path
import yaml

import pytest

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import load_config, AppConfig
from pydantic import ValidationError


class TestConfigVersioning:
    """Test config versioning system."""
    
    def test_version_1_config_without_monitoring(self):
        """Test that version 1 config works without monitoring section."""
        config_data = {
            "version": 1,
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should work - version 1 doesn't require monitoring
            config = load_config(temp_path)
            assert config["version"] == 1
            assert "monitoring" in config  # Should have default
            assert config["monitoring"]["enabled"] is False
            assert "dynamic_reloading" in config  # Should have default
            assert config["dynamic_reloading"]["enabled"] is False
        finally:
            os.unlink(temp_path)
    
    def test_version_1_implicit_without_monitoring(self):
        """Test that missing version defaults to 1 and works without monitoring."""
        config_data = {
            # No version specified - should default to 1
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should work - implicit version 1
            config = load_config(temp_path)
            assert config["version"] == 1
            assert "monitoring" in config
            assert "dynamic_reloading" in config
        finally:
            os.unlink(temp_path)
    
    def test_version_2_requires_monitoring(self):
        """Test that version 2 requires monitoring section."""
        config_data = {
            "version": 2,
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            }
            # Missing monitoring and dynamic_reloading sections
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should fail - version 2 requires monitoring
            with pytest.raises(ValueError) as exc_info:
                load_config(temp_path)
            assert "requires 'monitoring' section" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_version_2_with_all_required_sections(self):
        """Test that version 2 works with all required sections."""
        config_data = {
            "version": 2,
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            },
            "monitoring": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8080
            },
            "dynamic_reloading": {
                "enabled": False,
                "check_interval_seconds": 5
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should work - version 2 with all required sections
            config = load_config(temp_path)
            assert config["version"] == 2
            assert config["monitoring"]["enabled"] is True
            assert config["dynamic_reloading"]["enabled"] is False
        finally:
            os.unlink(temp_path)
    
    def test_version_2_requires_dynamic_reloading(self):
        """Test that version 2 requires dynamic_reloading section."""
        config_data = {
            "version": 2,
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            },
            "monitoring": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8080
            }
            # Missing dynamic_reloading section
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should fail - version 2 requires dynamic_reloading
            with pytest.raises(ValueError) as exc_info:
                load_config(temp_path)
            assert "requires 'dynamic_reloading' section" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_version_1_with_explicit_monitoring(self):
        """Test that version 1 can have explicit monitoring section."""
        config_data = {
            "version": 1,
            "database": {
                "path": "test.db",
                "preserve_existing_db": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            },
            "random_location": {
                "enabled": False
            },
            "monitoring": {
                "enabled": True,
                "host": "localhost",
                "port": 9090
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            # This should work - version 1 can have monitoring
            config = load_config(temp_path)
            assert config["version"] == 1
            assert config["monitoring"]["enabled"] is True
            assert config["monitoring"]["port"] == 9090
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])