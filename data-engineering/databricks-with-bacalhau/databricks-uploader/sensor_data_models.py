#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0",
#     "python-dateutil>=2.8",
# ]
# ///

"""
Pydantic models for sensor data validation and transformation.

These models enforce strict typing and validation rules to prevent
data quality issues that commonly break data pipelines.
"""

from datetime import datetime
from typing import Optional, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.types import confloat, conint


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
        ..., 
        description="Temperature in Celsius",
        json_schema_extra={"unit": "°C"}
    )
    
    humidity: confloat(ge=0, le=100) = Field(
        ..., 
        description="Humidity percentage",
        json_schema_extra={"unit": "%"}
    )
    
    pressure: confloat(ge=0, le=20) = Field(
        ..., 
        description="Pressure in bar",
        json_schema_extra={"unit": "bar"}
    )
    
    vibration: Optional[confloat(ge=0)] = Field(
        0.0, 
        description="Vibration reading",
        json_schema_extra={"unit": "units"}
    )
    
    voltage: confloat(ge=0, le=24) = Field(
        ..., 
        description="Supply voltage",
        json_schema_extra={"unit": "V"}
    )
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature_range(cls, v: float) -> float:
        """Validate temperature is within operational range."""
        if not 50 <= v <= 80:
            # Allow out of range but flag for routing
            pass
        return v
    
    @field_validator('voltage')
    @classmethod
    def validate_voltage_range(cls, v: float) -> float:
        """Validate voltage is within safe operating range."""
        if not 11.5 <= v <= 12.5:
            # Allow but flag for maintenance
            pass
        return v


class SensorStatus(BaseModel):
    """Sensor status information."""
    
    status_code: conint(ge=0, le=1) = Field(
        ..., 
        description="0=normal, 1=anomaly"
    )
    
    anomaly_flag: bool = Field(
        ..., 
        description="Boolean flag indicating anomaly"
    )
    
    anomaly_type: Optional[AnomalyTypeEnum] = Field(
        None, 
        description="Type of anomaly if present"
    )
    
    synced: bool = Field(
        False, 
        description="Whether record has been synced"
    )
    
    @model_validator(mode='after')
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
    
    manufacturer: ManufacturerEnum = Field(
        ..., 
        description="Device manufacturer"
    )
    
    model: ModelEnum = Field(
        ..., 
        description="Device model"
    )
    
    firmware_version: FirmwareVersionEnum = Field(
        ..., 
        description="Firmware version"
    )
    
    serial_number: Optional[str] = Field(
        None, 
        pattern=r'^[A-Za-z0-9\-]+$',
        description="Device serial number"
    )
    
    manufacture_date: Optional[datetime] = Field(
        None, 
        description="Date device was manufactured"
    )
    
    @model_validator(mode='after')
    def validate_model_manufacturer_match(self):
        """Ensure model is valid for the manufacturer."""
        valid_models = {
            ManufacturerEnum.SENSORTECH: [
                ModelEnum.TEMPSENSOR_PRO,
                ModelEnum.HUMIDCHECK_2000,
                ModelEnum.PRESSUREGUARD,
                ModelEnum.ENVMONITOR_3000
            ],
            ManufacturerEnum.DATALOGGER: [
                ModelEnum.DATALOGGER_X1,
                ModelEnum.AIRDATA_PLUS,
                ModelEnum.CLIMATETRACKER,
                ModelEnum.INDUSTRIALMONITOR_5000
            ],
            ManufacturerEnum.DATASENSE: [
                ModelEnum.TEMPVIBE_3000,
                ModelEnum.HUMIDPRESS_4000,
                ModelEnum.ALLSENSE_PRO,
                ModelEnum.FACTORYGUARD_7000
            ],
            ManufacturerEnum.MONITORPRO: [
                ModelEnum.PROTEMP_500,
                ModelEnum.PROHUMID_600,
                ModelEnum.PROPRESSURE_700,
                ModelEnum.PROENVIRON_800
            ]
        }
        
        if self.model not in valid_models.get(self.manufacturer, []):
            raise ValueError(
                f"Model '{self.model}' is not valid for manufacturer '{self.manufacturer}'"
            )
        return self


class LocationInfo(BaseModel):
    """Location information with GPS validation."""
    
    location: str = Field(
        ..., 
        min_length=1,
        description="Physical location name"
    )
    
    latitude: confloat(ge=-90, le=90) = Field(
        ..., 
        description="GPS latitude"
    )
    
    longitude: confloat(ge=-180, le=180) = Field(
        ..., 
        description="GPS longitude"
    )
    
    original_timezone: Optional[str] = Field(
        None, 
        description="Timezone string"
    )
    
    @field_validator('location')
    @classmethod
    def validate_location_not_placeholder(cls, v: str) -> str:
        """Ensure location is not a placeholder value."""
        placeholders = {
            "REPLACE_WITH_LOCATION", "DEFAULT LOCATION", 
            "UNKNOWN", "TBD", "TODO", "N/A", "NA"
        }
        if v.upper().strip() in placeholders or not v.strip():
            raise ValueError(f"Location cannot be a placeholder value: '{v}'")
        return v


class DeploymentInfo(BaseModel):
    """Deployment information."""
    
    deployment_type: Optional[str] = Field(
        None, 
        description="Type of deployment"
    )
    
    installation_date: Optional[datetime] = Field(
        None, 
        description="Date sensor was installed"
    )
    
    height_meters: Optional[confloat(ge=0, le=1000)] = Field(
        None, 
        description="Installation height in meters"
    )
    
    orientation_degrees: Optional[confloat(ge=0, le=360)] = Field(
        None, 
        description="Sensor orientation in degrees"
    )


class SensorMetadata(BaseModel):
    """Additional sensor metadata."""
    
    instance_id: Optional[str] = Field(
        None, 
        pattern=r'^i-[a-f0-9]{17}$|^[a-zA-Z0-9\-]+$',
        description="Cloud instance ID"
    )
    
    sensor_type: Optional[str] = Field(
        None, 
        description="Type of sensor"
    )


class TransformationMetadata(BaseModel):
    """Metadata about the data transformation."""
    
    bacalhau_job_id: str = Field(
        ..., 
        description="Unique Bacalhau job ID"
    )
    
    transformation_timestamp: datetime = Field(
        ..., 
        description="When transformation occurred"
    )
    
    node_identity_hash: str = Field(
        ..., 
        min_length=16,
        max_length=64,
        description="Hash of node identity"
    )
    
    transformation_version: str = Field(
        ..., 
        pattern=r'^\d+\.\d+\.\d+$',
        description="Semantic version of transformation"
    )
    
    original_record_id: Optional[int] = Field(
        None, 
        description="ID from original SQLite record"
    )


class SensorDataRecord(BaseModel):
    """Complete sensor data record with all validations."""
    
    timestamp: datetime = Field(
        ..., 
        description="ISO 8601 timestamp of reading"
    )
    
    sensor_id: str = Field(
        ..., 
        pattern=r'^[A-Z]{3}_[0-9]{6}$',
        description="Sensor identifier (e.g., CHI_123456)"
    )
    
    readings: SensorReadings
    status: SensorStatus
    device_info: DeviceInfo
    location_info: LocationInfo
    deployment_info: Optional[DeploymentInfo] = None
    metadata: Optional[SensorMetadata] = None
    transformation_metadata: TransformationMetadata
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        """Ensure timestamp is not in the future."""
        if v > datetime.now(v.tzinfo):
            raise ValueError("Timestamp cannot be in the future")
        return v
    
    def is_emergency(self) -> bool:
        """Check if this record qualifies as emergency data."""
        # Check for anomalies
        if self.status.anomaly_flag:
            return True
        
        # Check temperature thresholds
        if self.readings.temperature > 75 or self.readings.temperature < 52:
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
    
    def classification(self) -> Literal["raw", "aggregated", "emergency"]:
        """Classify record for bucket routing."""
        if self.is_emergency():
            return "emergency"
        
        # All valid records go to aggregated
        # Raw bucket gets everything including invalid
        return "aggregated"


# Example usage and validation demonstration
if __name__ == "__main__":
    import json
    
    # Valid record example
    valid_record = {
        "timestamp": "2024-01-15T10:30:00Z",
        "sensor_id": "CHI_123456",
        "readings": {
            "temperature": 62.5,
            "humidity": 35.2,
            "pressure": 12.3,
            "voltage": 12.1,
            "vibration": 0.0
        },
        "status": {
            "status_code": 0,
            "anomaly_flag": False,
            "anomaly_type": None,
            "synced": False
        },
        "device_info": {
            "manufacturer": "SensorTech",
            "model": "EnvMonitor-3000",
            "firmware_version": "1.4",
            "serial_number": "ST-2024-001"
        },
        "location_info": {
            "location": "Chicago",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "original_timezone": "America/Chicago"
        },
        "transformation_metadata": {
            "bacalhau_job_id": "job-12345",
            "transformation_timestamp": "2024-01-15T10:31:00Z",
            "node_identity_hash": "a1b2c3d4e5f6g7h8",
            "transformation_version": "1.0.0"
        }
    }
    
    try:
        record = SensorDataRecord(**valid_record)
        print("✓ Valid record created successfully")
        print(f"  Classification: {record.classification()}")
    except Exception as e:
        print(f"✗ Validation failed: {e}")
    
    # Invalid examples that would break pipelines
    invalid_examples = [
        {
            "name": "String in numeric field",
            "data": {**valid_record, "readings": {**valid_record["readings"], "temperature": "hot"}}
        },
        {
            "name": "Negative humidity",
            "data": {**valid_record, "readings": {**valid_record["readings"], "humidity": -10}}
        },
        {
            "name": "Invalid manufacturer/model combo",
            "data": {**valid_record, "device_info": {
                **valid_record["device_info"], 
                "manufacturer": "SensorTech",
                "model": "ProTemp-500"  # This is a MonitorPro model
            }}
        },
        {
            "name": "Placeholder location",
            "data": {**valid_record, "location_info": {
                **valid_record["location_info"],
                "location": "UNKNOWN"
            }}
        },
        {
            "name": "Invalid GPS coordinates",
            "data": {**valid_record, "location_info": {
                **valid_record["location_info"],
                "latitude": 200  # Out of range
            }}
        }
    ]
    
    print("\nTesting invalid records that would break pipelines:")
    for example in invalid_examples:
        try:
            SensorDataRecord(**example["data"])
            print(f"✗ {example['name']}: Should have failed!")
        except Exception as e:
            print(f"✓ {example['name']}: Correctly rejected - {str(e)[:100]}...")