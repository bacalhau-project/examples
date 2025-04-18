"""
Configuration models for the Sensor Manager.

Uses Pydantic for validation and serialization of configuration data.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import os

try:
    from pydantic import BaseModel, Field, root_validator
except ImportError:
    print("Pydantic is not installed. Please install it with: pip install pydantic")
    
    # Define minimal BaseModel for fallback
    class BaseModel:
        pass
    
    Field = lambda *args, **kwargs: None
    root_validator = lambda *args, **kwargs: lambda f: f


class SensorConfig(BaseModel):
    """Configuration for sensor simulation."""
    
    id: Optional[str] = Field(None, description="Unique sensor identifier")
    type: str = Field("temperature_vibration", description="Type of sensor")
    location: str = Field("Factory Floor A", description="Physical location")
    manufacturer: str = Field("SensorTech", description="Manufacturer name")
    model: str = Field("TempVibe-2000", description="Model number")
    firmware_version: str = Field("1.3", description="Firmware version")


class SimulationConfig(BaseModel):
    """Configuration for simulation parameters."""
    
    readings_per_second: int = Field(1, description="Number of readings per second")
    run_time_seconds: int = Field(360000, description="Total simulation duration")


class DatabaseConfig(BaseModel):
    """Configuration for the SQLite database."""
    
    path: str = Field("data/sensor_data.db", description="Path to SQLite database file")
    backup_enabled: bool = Field(False, description="Enable automatic backups")
    backup_interval_hours: int = Field(24, description="Backup interval in hours")
    backup_path: str = Field("/app/data/backups/", description="Where to store backups")
    batch_size: int = Field(100, description="Number of readings to insert in a batch")


class RandomLocationConfig(BaseModel):
    """Configuration for random location generation."""
    
    enabled: bool = Field(True, description="Enable random location generation")
    number_of_cities: int = Field(10, description="Number of cities to use")
    gps_variation: int = Field(100, description="Variation around city center (meters)")
    cities_file: str = Field("src/cities.json", description="Path to cities file")


class SensorManagerConfig(BaseModel):
    """Main configuration for the Sensor Manager."""
    
    sensor: SensorConfig = Field(default_factory=SensorConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    random_location: RandomLocationConfig = Field(default_factory=RandomLocationConfig)
    sensors_per_city: int = Field(5, description="Number of sensors per city")
    max_cities: int = Field(5, description="Maximum number of cities to use")
    readings_per_second: int = Field(1, description="Number of readings per second")
    anomaly_probability: float = Field(0.05, description="Probability of anomalies")
    upload_interval: int = Field(30, description="Interval for uploader in seconds")
    archive_format: str = Field("Parquet", description="Format for archived data")
    config_file: str = Field("config.yaml", description="Path to configuration file")


def load_config(config_path: Union[str, Path]) -> SensorManagerConfig:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        SensorManagerConfig object
    """
    try:
        import yaml
        
        config_path = Path(config_path)
        if not config_path.exists():
            print(f"Warning: Config file '{config_path}' not found, using defaults")
            return SensorManagerConfig()
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        return SensorManagerConfig(**config_data)
        
    except ImportError:
        print("PyYAML is not installed. Please install it with: pip install pyyaml")
        return SensorManagerConfig()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return SensorManagerConfig()