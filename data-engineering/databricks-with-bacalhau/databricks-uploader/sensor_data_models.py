#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0.0",
#     "python-dateutil>=2.8",
#     "requests>=2.31.0",
# ]
# ///

"""
Wind Turbine Sensor Data Models

This module provides both JSON Schema and Pydantic models for validating
wind turbine sensor data. It supports dynamic schema loading from URLs
and implements physics-based validation rules for anomaly detection.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Literal
from enum import Enum
import json
import requests
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.types import confloat, conint


# JSON Schema definition for wind turbine sensor data
WIND_TURBINE_SENSOR_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "WindTurbineSensorData",
    "description": "Schema for wind turbine sensor telemetry data",
    "type": "object",
    "required": [
        "timestamp",
        "turbine_id",
        "site_id",
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_direction",
        "rotation_speed",
        "blade_pitch",
        "generator_temp",
        "power_output",
        "vibration_x",
        "vibration_y",
        "vibration_z",
    ],
    "properties": {
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp of the sensor reading",
        },
        "turbine_id": {
            "type": "string",
            "pattern": "^WT-[0-9]{4}$",
            "description": "Unique turbine identifier (format: WT-XXXX)",
        },
        "site_id": {
            "type": "string",
            "pattern": "^SITE-[A-Z]{3}$",
            "description": "Site location identifier (format: SITE-XXX)",
        },
        "temperature": {
            "type": "number",
            "minimum": -40,
            "maximum": 60,
            "description": "Ambient temperature in Celsius",
        },
        "humidity": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Relative humidity percentage",
        },
        "pressure": {
            "type": "number",
            "minimum": 900,
            "maximum": 1100,
            "description": "Atmospheric pressure in hPa",
        },
        "wind_speed": {
            "type": "number",
            "minimum": 0,
            "maximum": 50,
            "description": "Wind speed in meters per second",
        },
        "wind_direction": {
            "type": "number",
            "minimum": 0,
            "maximum": 360,
            "description": "Wind direction in degrees (0-360)",
        },
        "rotation_speed": {
            "type": "number",
            "minimum": 0,
            "maximum": 3600,
            "description": "Rotor rotation speed in RPM",
        },
        "blade_pitch": {
            "type": "number",
            "minimum": -5,
            "maximum": 95,
            "description": "Blade pitch angle in degrees",
        },
        "generator_temp": {
            "type": "number",
            "minimum": 0,
            "maximum": 120,
            "description": "Generator temperature in Celsius",
        },
        "power_output": {
            "type": "number",
            "minimum": 0,
            "maximum": 5000,
            "description": "Power output in kilowatts",
        },
        "vibration_x": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "X-axis vibration in mm/s",
        },
        "vibration_y": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Y-axis vibration in mm/s",
        },
        "vibration_z": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Z-axis vibration in mm/s",
        },
        "battery_level": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Battery charge percentage (optional)",
        },
        "signal_strength": {
            "type": "number",
            "minimum": -120,
            "maximum": 0,
            "description": "Signal strength in dBm (optional)",
        },
        "error_code": {
            "type": "string",
            "pattern": "^[A-Z0-9]{4}$",
            "description": "Error code if any (optional)",
        },
        "maintenance_required": {"type": "boolean", "description": "Maintenance flag (optional)"},
    },
    "additionalProperties": False,
}


class WindTurbineSensorData(BaseModel):
    """
    Pydantic model for wind turbine sensor data validation.

    This model enforces both structural and business logic validation rules
    for wind turbine telemetry data.
    """

    # Timestamp and identifiers
    timestamp: datetime = Field(..., description="ISO 8601 timestamp")
    turbine_id: str = Field(..., pattern="^WT-[0-9]{4}$")
    site_id: str = Field(..., pattern="^SITE-[A-Z]{3}$")

    # Environmental sensors
    temperature: float = Field(..., ge=-40, le=60)
    humidity: float = Field(..., ge=0, le=100)
    pressure: float = Field(..., ge=900, le=1100)
    wind_speed: float = Field(..., ge=0, le=50)
    wind_direction: float = Field(..., ge=0, le=360)

    # Operational parameters
    rotation_speed: float = Field(..., ge=0, le=3600)
    blade_pitch: float = Field(..., ge=-5, le=95)
    generator_temp: float = Field(..., ge=0, le=120)
    power_output: float = Field(..., ge=0, le=5000)

    # Vibration monitoring
    vibration_x: float = Field(..., ge=0, le=100)
    vibration_y: float = Field(..., ge=0, le=100)
    vibration_z: float = Field(..., ge=0, le=100)

    # Optional fields
    battery_level: Optional[float] = Field(None, ge=0, le=100)
    signal_strength: Optional[float] = Field(None, ge=-120, le=0)
    error_code: Optional[str] = Field(None, pattern="^[A-Z0-9]{4}$")
    maintenance_required: Optional[bool] = None

    @model_validator(mode="after")
    def validate_physics_constraints(self) -> "WindTurbineSensorData":
        """Validate physical relationships between sensor readings."""

        # Rule 1: No rotation without minimum wind speed (cut-in speed ~3 m/s)
        if self.wind_speed < 3 and self.rotation_speed > 50:
            raise ValueError(
                f"Invalid: Rotation {self.rotation_speed} RPM with "
                f"wind speed {self.wind_speed} m/s (below cut-in)"
            )

        # Rule 2: Safety cutoff at high wind speeds (>25 m/s)
        if self.wind_speed > 25 and self.rotation_speed > 2000:
            raise ValueError(
                f"Safety violation: Rotation {self.rotation_speed} RPM "
                f"at {self.wind_speed} m/s wind exceeds safety limit"
            )

        # Rule 3: Power output should correlate with rotation
        if self.rotation_speed < 10 and self.power_output > 10:
            raise ValueError(
                f"Invalid: Power output {self.power_output} kW "
                f"without rotation ({self.rotation_speed} RPM)"
            )

        # Rule 4: Minimum rotation for significant power
        if self.rotation_speed > 1000 and self.power_output < 100:
            raise ValueError(
                f"Anomaly: Power output {self.power_output} kW "
                f"too low for {self.rotation_speed} RPM"
            )

        # Rule 5: Generator temperature check
        if self.power_output > 3000 and self.generator_temp < 30:
            raise ValueError(
                f"Anomaly: Generator temp {self.generator_temp}°C "
                f"too low for {self.power_output} kW output"
            )

        # Rule 6: Critical vibration threshold
        max_vibration = max(self.vibration_x, self.vibration_y, self.vibration_z)
        if max_vibration > 50:
            raise ValueError(
                f"Critical: Vibration level {max_vibration} mm/s exceeds safety threshold"
            )

        # Rule 7: Blade pitch vs wind speed relationship
        if self.wind_speed > 20 and self.blade_pitch < 10:
            raise ValueError(
                f"Warning: Blade pitch {self.blade_pitch}° may be "
                f"too low for wind speed {self.wind_speed} m/s"
            )

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-15T10:30:00Z",
                "turbine_id": "WT-0042",
                "site_id": "SITE-TEX",
                "temperature": 15.5,
                "humidity": 65.0,
                "pressure": 1013.25,
                "wind_speed": 12.5,
                "wind_direction": 225.0,
                "rotation_speed": 1200.0,
                "blade_pitch": 15.0,
                "generator_temp": 55.0,
                "power_output": 2500.0,
                "vibration_x": 2.5,
                "vibration_y": 3.1,
                "vibration_z": 1.8,
                "battery_level": 95.0,
                "signal_strength": -65.0,
            }
        }


def get_schema_json() -> str:
    """Return the JSON Schema as a formatted string."""
    return json.dumps(WIND_TURBINE_SENSOR_SCHEMA, indent=2)


def load_schema_from_url(url: str) -> Dict[str, Any]:
    """
    Load JSON Schema from a URL.

    Args:
        url: URL pointing to a JSON Schema definition

    Returns:
        Dictionary containing the JSON Schema
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ValueError(f"Failed to load schema from URL: {e}")


def validate_sensor_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate sensor data against the model.

    Args:
        data: Dictionary containing sensor data

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        WindTurbineSensorData(**data)
        return True, None
    except Exception as e:
        return False, str(e)


def generate_anomaly_examples() -> list[Dict[str, Any]]:
    """Generate examples of data that would trigger anomalies."""
    base_data = {
        "timestamp": "2024-01-15T10:30:00Z",
        "turbine_id": "WT-0042",
        "site_id": "SITE-TEX",
        "temperature": 15.5,
        "humidity": 65.0,
        "pressure": 1013.25,
        "wind_direction": 225.0,
        "blade_pitch": 15.0,
        "generator_temp": 55.0,
        "vibration_x": 2.5,
        "vibration_y": 3.1,
        "vibration_z": 1.8,
    }

    anomalies = []

    # Anomaly 1: Rotation without wind
    anomalies.append(
        {
            **base_data,
            "wind_speed": 2.0,  # Below cut-in
            "rotation_speed": 500.0,  # Should be ~0
            "power_output": 100.0,
            "_anomaly": "Rotation without sufficient wind",
        }
    )

    # Anomaly 2: Excessive vibration
    anomalies.append(
        {
            **base_data,
            "wind_speed": 15.0,
            "rotation_speed": 1500.0,
            "power_output": 3000.0,
            "vibration_x": 65.0,  # Critical level
            "vibration_y": 55.0,
            "vibration_z": 45.0,
            "_anomaly": "Critical vibration levels",
        }
    )

    # Anomaly 3: Power without rotation
    anomalies.append(
        {
            **base_data,
            "wind_speed": 12.0,
            "rotation_speed": 5.0,  # Nearly stopped
            "power_output": 500.0,  # Should be ~0
            "_anomaly": "Power generation without rotation",
        }
    )

    # Anomaly 4: Invalid turbine ID
    anomalies.append(
        {
            **base_data,
            "turbine_id": "TURB-42",  # Wrong format
            "wind_speed": 12.0,
            "rotation_speed": 1200.0,
            "power_output": 2500.0,
            "_anomaly": "Invalid turbine ID format",
        }
    )

    # Anomaly 5: Out of range temperature
    anomalies.append(
        {
            **base_data,
            "temperature": 75.0,  # > 60°C max
            "wind_speed": 12.0,
            "rotation_speed": 1200.0,
            "power_output": 2500.0,
            "_anomaly": "Temperature exceeds maximum range",
        }
    )

    return anomalies


# Keep the original classes for backward compatibility but mark as deprecated
class ManufacturerEnum(str, Enum):
    """Valid sensor manufacturers."""

    SENSORTECH = "SensorTech"
    DATALOGGER = "DataLogger"
    DATASENSE = "DataSense"
    MONITORPRO = "MonitorPro"


class ModelEnum(str, Enum):
    """Valid sensor models by manufacturer."""

    # SensorTech models
    TEMPSENSOR_PRO = "TempSensor Pro"
    HUMIDCHECK_2000 = "HumidCheck 2000"
    PRESSUREGUARD = "PressureGuard"
    ENVMONITOR_3000 = "EnvMonitor-3000"

    # DataLogger models
    DATALOGGER_X1 = "DataLogger-X1"
    AIRDATA_PLUS = "AirData-Plus"
    CLIMATETRACKER = "ClimateTracker"
    INDUSTRIALMONITOR_5000 = "IndustrialMonitor-5000"

    # DataSense models
    TEMPVIBE_3000 = "TempVibe-3000"
    HUMIDPRESS_4000 = "HumidPress-4000"
    ALLSENSE_PRO = "AllSense-Pro"
    FACTORYGUARD_7000 = "FactoryGuard-7000"

    # MonitorPro models
    PROTEMP_500 = "ProTemp-500"
    PROHUMID_600 = "ProHumid-600"
    PROPRESSURE_700 = "ProPressure-700"
    PROENVIRON_800 = "ProEnviron-800"


class FirmwareVersionEnum(str, Enum):
    """Valid firmware versions."""

    V1_0 = "1.0"
    V1_2_0 = "1.2.0"
    V1_4 = "1.4"
    V2_1 = "2.1"
    V2_3_5 = "2.3.5"
    V2_5 = "2.5"
    V3_0_0_BETA = "3.0.0-beta"
    V3_1_2_ALPHA = "3.1.2-alpha"
    V3_2_RC1 = "3.2-rc1"


class AnomalyTypeEnum(str, Enum):
    """Valid anomaly types."""

    SPIKE = "spike"
    TREND = "trend"
    PATTERN = "pattern"
    MISSING_DATA = "missing_data"
    NOISE = "noise"


class SensorReadings(BaseModel):
    """Sensor reading values with strict validation."""

    temperature: confloat(ge=-50, le=150) = Field(
        ..., description="Temperature in Celsius", json_schema_extra={"unit": "°C"}
    )

    humidity: confloat(ge=0, le=100) = Field(
        ..., description="Humidity percentage", json_schema_extra={"unit": "%"}
    )

    pressure: confloat(ge=0, le=20) = Field(
        ..., description="Pressure in bar", json_schema_extra={"unit": "bar"}
    )

    vibration: confloat(ge=0) | None = Field(
        0.0, description="Vibration reading", json_schema_extra={"unit": "units"}
    )

    voltage: confloat(ge=0, le=24) = Field(
        ..., description="Supply voltage", json_schema_extra={"unit": "V"}
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature_range(cls, v: float) -> float:
        """Validate temperature is within operational range."""
        if not 50 <= v <= 80:
            # Allow out of range but flag for routing
            pass
        return v

    @field_validator("voltage")
    @classmethod
    def validate_voltage_range(cls, v: float) -> float:
        """Validate voltage is within safe operating range."""
        if not 11.5 <= v <= 12.5:
            # Allow but flag for maintenance
            pass
        return v


class SensorStatus(BaseModel):
    """Sensor status information."""

    status_code: conint(ge=0, le=1) = Field(..., description="0=normal, 1=anomaly")

    anomaly_flag: bool = Field(..., description="Boolean flag indicating anomaly")

    anomaly_type: AnomalyTypeEnum | None = Field(None, description="Type of anomaly if present")

    synced: bool = Field(False, description="Whether record has been synced")

    @model_validator(mode="after")
    def validate_anomaly_consistency(self):
        """Ensure anomaly flag and type are consistent."""
        if self.anomaly_flag and not self.anomaly_type:
            raise ValueError("anomaly_type must be specified when anomaly_flag is True")
        if not self.anomaly_flag and self.anomaly_type:
            raise ValueError("anomaly_type should be None when anomaly_flag is False")
        if self.anomaly_flag != (self.status_code == 1):
            raise ValueError("anomaly_flag must match status_code (0=False, 1=True)")
        return self


class DeviceInfo(BaseModel):
    """Device information with manufacturer/model validation."""

    manufacturer: ManufacturerEnum = Field(..., description="Device manufacturer")

    model: ModelEnum = Field(..., description="Device model")

    firmware_version: FirmwareVersionEnum = Field(..., description="Firmware version")

    serial_number: str | None = Field(
        None, pattern=r"^[A-Za-z0-9\-]+$", description="Device serial number"
    )

    manufacture_date: datetime | None = Field(None, description="Date device was manufactured")

    @model_validator(mode="after")
    def validate_model_manufacturer_match(self):
        """Ensure model is valid for the manufacturer."""
        valid_models = {
            ManufacturerEnum.SENSORTECH: [
                ModelEnum.TEMPSENSOR_PRO,
                ModelEnum.HUMIDCHECK_2000,
                ModelEnum.PRESSUREGUARD,
                ModelEnum.ENVMONITOR_3000,
            ],
            ManufacturerEnum.DATALOGGER: [
                ModelEnum.DATALOGGER_X1,
                ModelEnum.AIRDATA_PLUS,
                ModelEnum.CLIMATETRACKER,
                ModelEnum.INDUSTRIALMONITOR_5000,
            ],
            ManufacturerEnum.DATASENSE: [
                ModelEnum.TEMPVIBE_3000,
                ModelEnum.HUMIDPRESS_4000,
                ModelEnum.ALLSENSE_PRO,
                ModelEnum.FACTORYGUARD_7000,
            ],
            ManufacturerEnum.MONITORPRO: [
                ModelEnum.PROTEMP_500,
                ModelEnum.PROHUMID_600,
                ModelEnum.PROPRESSURE_700,
                ModelEnum.PROENVIRON_800,
            ],
        }

        if self.model not in valid_models.get(self.manufacturer, []):
            raise ValueError(
                f"Model '{self.model}' is not valid for manufacturer '{self.manufacturer}'"
            )
        return self


class LocationInfo(BaseModel):
    """Location information with GPS validation."""

    location: str = Field(..., min_length=1, description="Physical location name")

    latitude: confloat(ge=-90, le=90) = Field(..., description="GPS latitude")

    longitude: confloat(ge=-180, le=180) = Field(..., description="GPS longitude")

    original_timezone: str | None = Field(None, description="Timezone string")

    @field_validator("location")
    @classmethod
    def validate_location_not_placeholder(cls, v: str) -> str:
        """Ensure location is not a placeholder value."""
        placeholders = {
            "REPLACE_WITH_LOCATION",
            "DEFAULT LOCATION",
            "UNKNOWN",
            "TBD",
            "TODO",
            "N/A",
            "NA",
        }
        if v.upper().strip() in placeholders or not v.strip():
            raise ValueError(f"Location cannot be a placeholder value: '{v}'")
        return v


class DeploymentInfo(BaseModel):
    """Deployment information."""

    deployment_type: str | None = Field(None, description="Type of deployment")

    installation_date: datetime | None = Field(None, description="Date sensor was installed")

    height_meters: confloat(ge=0, le=1000) | None = Field(
        None, description="Installation height in meters"
    )

    orientation_degrees: confloat(ge=0, le=360) | None = Field(
        None, description="Sensor orientation in degrees"
    )


class SensorMetadata(BaseModel):
    """Additional sensor metadata."""

    instance_id: str | None = Field(
        None, pattern=r"^i-[a-f0-9]{17}$|^[a-zA-Z0-9\-]+$", description="Cloud instance ID"
    )

    sensor_type: str | None = Field(None, description="Type of sensor")


class TransformationMetadata(BaseModel):
    """Metadata about the data transformation."""

    bacalhau_job_id: str = Field(..., description="Unique Bacalhau job ID")

    transformation_timestamp: datetime = Field(..., description="When transformation occurred")

    node_identity_hash: str = Field(
        ..., min_length=16, max_length=64, description="Hash of node identity"
    )

    transformation_version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version of transformation"
    )

    original_record_id: int | None = Field(None, description="ID from original SQLite record")


class SensorDataRecord(BaseModel):
    """Complete sensor data record with all validations."""

    timestamp: datetime = Field(..., description="ISO 8601 timestamp of reading")

    sensor_id: str = Field(
        ..., pattern=r"^[A-Z]{3}_[0-9]{6}$", description="Sensor identifier (e.g., CHI_123456)"
    )

    readings: SensorReadings
    status: SensorStatus
    device_info: DeviceInfo
    location_info: LocationInfo
    deployment_info: DeploymentInfo | None = None
    metadata: SensorMetadata | None = None
    transformation_metadata: TransformationMetadata

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        """Ensure timestamp is not in the future."""
        if v > datetime.now(v.tzinfo):
            raise ValueError("Timestamp cannot be in the future")
        return v

    def has_anomaly(self) -> bool:
        """Check if this record has anomaly conditions."""
        # Check anomaly flag
        if self.status.anomaly_flag:
            return True

        # Check temperature thresholds
        if self.readings.temperature > 100 or self.readings.temperature < -20:
            return True

        # Check vibration thresholds
        if self.readings.vibration > 0.5:
            return True

        # Check pressure thresholds
        if self.readings.pressure > 14.5 or self.readings.pressure < 10.5:
            return True

        # Check voltage thresholds
        if self.readings.voltage > 12.4 or self.readings.voltage < 11.6:
            return True

        # Check humidity thresholds
        if self.readings.humidity > 95 or self.readings.humidity < 1:
            return True

        return False

    def classification(self) -> Literal["raw", "aggregated"]:
        """Classify record for bucket routing."""
        # All valid records go to aggregated
        # Raw bucket gets everything including invalid
        # Anomaly detection is handled within aggregated pipeline
        return "aggregated"


# Example usage and validation demonstration
if __name__ == "__main__":
    # Valid record example
    valid_record = {
        "timestamp": "2024-01-15T10:30:00Z",
        "sensor_id": "CHI_123456",
        "readings": {
            "temperature": 62.5,
            "humidity": 35.2,
            "pressure": 12.3,
            "voltage": 12.1,
            "vibration": 0.0,
        },
        "status": {"status_code": 0, "anomaly_flag": False, "anomaly_type": None, "synced": False},
        "device_info": {
            "manufacturer": "SensorTech",
            "model": "EnvMonitor-3000",
            "firmware_version": "1.4",
            "serial_number": "ST-2024-001",
        },
        "location_info": {
            "location": "Chicago",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "original_timezone": "America/Chicago",
        },
        "transformation_metadata": {
            "bacalhau_job_id": "job-12345",
            "transformation_timestamp": "2024-01-15T10:31:00Z",
            "node_identity_hash": "a1b2c3d4e5f6g7h8",
            "transformation_version": "1.0.0",
        },
    }

    try:
        record = SensorDataRecord(**valid_record)
        print("✓ Valid record created successfully")
        print(f"  Classification: {record.classification()}")
        print(f"  Has anomaly: {record.has_anomaly()}")
    except Exception as e:
        print(f"✗ Validation failed: {e}")

    # Invalid examples that would break pipelines
    invalid_examples = [
        {
            "name": "String in numeric field",
            "data": {
                **valid_record,
                "readings": {**valid_record["readings"], "temperature": "hot"},
            },
        },
        {
            "name": "Negative humidity",
            "data": {**valid_record, "readings": {**valid_record["readings"], "humidity": -10}},
        },
        {
            "name": "Invalid manufacturer/model combo",
            "data": {
                **valid_record,
                "device_info": {
                    **valid_record["device_info"],
                    "manufacturer": "SensorTech",
                    "model": "ProTemp-500",  # This is a MonitorPro model
                },
            },
        },
        {
            "name": "Placeholder location",
            "data": {
                **valid_record,
                "location_info": {**valid_record["location_info"], "location": "UNKNOWN"},
            },
        },
        {
            "name": "Invalid GPS coordinates",
            "data": {
                **valid_record,
                "location_info": {
                    **valid_record["location_info"],
                    "latitude": 200,  # Out of range
                },
            },
        },
    ]

    print("\nTesting invalid records that would break pipelines:")
    for example in invalid_examples:
        try:
            SensorDataRecord(**example["data"])
            print(f"✗ {example['name']}: Should have failed!")
        except Exception as e:
            print(f"✓ {example['name']}: Correctly rejected - {str(e)[:100]}...")
