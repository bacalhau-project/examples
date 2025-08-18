import logging
import os
import random
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from .enums import AnomalyType, FirmwareVersion, Model, ParameterType

logger = logging.getLogger(__name__)
# Inherit parent logger's level
logger.setLevel(logging.getLogger().level)


class AnomalyGenerator:
    def __init__(self, config, identity):
        """Initialize the anomaly generator with configuration.

        Args:
            config: Anomaly configuration
            identity: Sensor identity configuration

        Raises:
            ValueError: If any of the identity values are invalid
        """
        self.config = config
        self.anomaly_config = config.get("anomalies", {})
        self.enabled = self.anomaly_config.get("enabled", False)
        self.probability = self.anomaly_config.get("probability", 0.05)
        self.types = self.anomaly_config.get("types", {})

        # Get sensor ID - handle both old and new formats
        self.id = identity.get("sensor_id") or identity.get("id")
        if not self.id:
            raise ValueError("Sensor ID is required in identity configuration")

        # Extract device info based on format
        device_info = identity.get("device_info", {})
        
        # Initialize identity with validation - check nested first, then flat
        firmware_val = device_info.get("firmware_version") or identity.get("firmware_version")
        if not self._is_valid_semver(firmware_val):
            raise ValueError(
                f"Invalid firmware version: {firmware_val}. "
                f"Must be a valid semantic version (e.g., 1.0.0, 2.1.3-beta, 1.0.0+build123)"
            )
        # Try to convert to enum if possible, otherwise keep as string
        try:
            self.firmware_version = FirmwareVersion(firmware_val)
        except (ValueError, KeyError):
            # Not a known enum value, keep as string for flexibility
            self.firmware_version = firmware_val

        model_val = device_info.get("model") or identity.get("model")
        # Try to convert to enum if possible, otherwise keep as string
        try:
            self.model = Model(model_val)
        except (ValueError, KeyError):
            # Not a known enum value, keep as string for flexibility
            self.model = model_val

        manufacturer_val = device_info.get("manufacturer") or identity.get("manufacturer")
        if not manufacturer_val:
            raise ValueError("Manufacturer is required in identity configuration")
        # Accept any string as manufacturer
        self.manufacturer = manufacturer_val

        # Extract location data based on format
        location_data = identity.get("location")
        if isinstance(location_data, dict):
            # New nested format
            self.location = location_data.get("city") or location_data.get("address")
            coords = location_data.get("coordinates", {})
            self.latitude = coords.get("latitude", identity.get("latitude"))
            self.longitude = coords.get("longitude", identity.get("longitude"))
        else:
            # Legacy flat format
            self.location = location_data
            self.latitude = identity.get("latitude")
            self.longitude = identity.get("longitude")
            
        if not self.location:
            raise ValueError("Location is required in identity configuration")

        # Track active anomalies
        self.active_anomalies = {}
        self.start_times = {}
        
        # Debug mode
        self.debug_mode = os.environ.get('DEBUG_MODE') == 'true' or logger.isEnabledFor(logging.DEBUG)
        if self.debug_mode:
            logger.setLevel(logging.DEBUG)

        # Log sensor identity
        logger.info(f"Initializing anomaly generator for sensor: {self.id}")
        logger.info(f"  Firmware: {self.firmware_version}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Manufacturer: {self.manufacturer}")
        
        if self.debug_mode:
            logger.debug(f"🔍 Anomaly config: enabled={self.enabled}, probability={self.probability}, types={list(self.types.keys())}")

    def _is_valid_semver(self, version: str) -> bool:
        """Validate if a string is a valid semantic version.
        
        Args:
            version: Version string to validate
            
        Returns:
            True if valid SemVer, False otherwise
        """
        # SemVer regex pattern
        # Matches: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
        semver_pattern = r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
        return bool(re.match(semver_pattern, version))

    def should_generate_anomaly(self):
        """Determine if an anomaly should be generated based on probability and firmware version."""
        if not self.enabled:
            return False

        # Adjust probability based on firmware version
        adjusted_probability = self.probability

        # Handle both enum and string firmware versions
        fw_version = self.firmware_version
        if hasattr(fw_version, 'value'):
            fw_version = fw_version.value
            
        # Firmware 1.4 has higher anomaly probability
        if fw_version in ["1.4", "1.4.0"]:
            adjusted_probability *= 1.5  # 50% more anomalies

        # Firmware 1.5 has lower anomaly probability
        elif fw_version in ["1.5", "1.5.0"]:
            adjusted_probability *= 0.7  # 30% fewer anomalies

        should_generate = random.random() < adjusted_probability
        
        if self.debug_mode and should_generate:
            logger.debug(f"🎲 Anomaly generation triggered (probability: {adjusted_probability:.3f})")
        
        return should_generate

    def select_anomaly_type(self):
        """Select an anomaly type based on configured weights and sensor characteristics."""
        # Filter enabled anomaly types
        enabled_types = {}
        for anomaly_type, config in self.types.items():
            if config.get("enabled", True):
                enabled_types[AnomalyType(anomaly_type)] = config.get("weight", 1.0)

        if not enabled_types:
            return None

        # Adjust weights based on model
        if self.model == "EnvMonitor-3000":
            # More prone to missing data
            if AnomalyType.MISSING_DATA in enabled_types:
                enabled_types[AnomalyType.MISSING_DATA] *= 2.0
        elif self.model == "EnvMonitor-4000":
            # More prone to pattern anomalies
            if AnomalyType.PATTERN in enabled_types:
                enabled_types[AnomalyType.PATTERN] *= 1.5
        elif self.model == "EnvMonitor-5000":
            # More prone to spike anomalies
            if AnomalyType.SPIKE in enabled_types:
                enabled_types[AnomalyType.SPIKE] *= 1.5

        # Adjust weights based on firmware
        if self.firmware_version == "1.4" or self.firmware_version == "1.4.0":
            # More temperature spikes and noise
            if AnomalyType.SPIKE in enabled_types:
                enabled_types[AnomalyType.SPIKE] *= 1.3
            if AnomalyType.NOISE in enabled_types:
                enabled_types[AnomalyType.NOISE] *= 1.5
        elif self.firmware_version == "1.5" or self.firmware_version == "1.5.0":
            # Fewer spikes, more stable
            if AnomalyType.SPIKE in enabled_types:
                enabled_types[AnomalyType.SPIKE] *= 0.7
            if AnomalyType.NOISE in enabled_types:
                enabled_types[AnomalyType.NOISE] *= 0.8

        # Normalize weights
        total_weight = sum(enabled_types.values())
        normalized_weights = {k: v / total_weight for k, v in enabled_types.items()}

        # Select based on weights
        r = random.random()
        cumulative = 0
        for anomaly_type, weight in normalized_weights.items():
            cumulative += weight
            if r <= cumulative:
                return anomaly_type

        # Fallback
        return list(enabled_types.keys())[0]

    def start_anomaly(self, anomaly_type):
        """Start an anomaly of the specified type."""
        if anomaly_type in self.active_anomalies:
            return  # Already active

        self.active_anomalies[anomaly_type] = True
        self.start_times[anomaly_type] = time.time()
        logger.info(f"Started {anomaly_type.value} anomaly")

    def is_anomaly_active(self, anomaly_type):
        """Check if an anomaly is currently active."""
        if (
            anomaly_type not in self.active_anomalies
            or not self.active_anomalies[anomaly_type]
        ):
            return False

        # Check if the anomaly duration has expired
        start_time = self.start_times.get(anomaly_type, 0)
        duration = self.types.get(anomaly_type.value, {}).get("duration_seconds", 60)

        if time.time() - start_time > duration:
            self.active_anomalies[anomaly_type] = False
            logger.info(f"Ended {anomaly_type.value} anomaly")
            return False

        return True

    def apply_anomaly(self, reading, anomaly_type):
        """Apply the specified anomaly to the sensor reading."""
        if anomaly_type == AnomalyType.SPIKE:
            return self._apply_spike_anomaly(reading)
        elif anomaly_type == AnomalyType.TREND:
            return self._apply_trend_anomaly(reading)
        elif anomaly_type == AnomalyType.PATTERN:
            return self._apply_pattern_anomaly(reading)
        elif anomaly_type == AnomalyType.MISSING_DATA:
            return self._apply_missing_data_anomaly(reading)
        elif anomaly_type == AnomalyType.NOISE:
            return self._apply_noise_anomaly(reading)
        else:
            return reading, False, None

    def _apply_spike_anomaly(self, reading):
        """Apply a spike anomaly to the reading."""
        # Choose a random parameter to spike
        params = [
            ParameterType.TEMPERATURE,
            ParameterType.HUMIDITY,
            ParameterType.VOLTAGE,
        ]

        # For firmware 1.3, temperature spikes are more common
        if self.firmware_version == FirmwareVersion.V1_4:
            if random.random() < 0.6:  # 60% chance to choose temperature
                param = ParameterType.TEMPERATURE
            else:
                param = random.choice([ParameterType.HUMIDITY, ParameterType.VOLTAGE])
        else:
            param = random.choice(params)

        # Create a copy of the reading
        modified = reading.copy()

        # Apply a spike using standard deviations
        # Get the normal parameters for this metric to calculate proper spike
        normal_params = self.config.get("normal_parameters", {}).get(param.value, {})
        current_value = reading[param.value]
        
        if "mean" in normal_params and "std_dev" in normal_params:
            mean = normal_params["mean"]
            std_dev = normal_params["std_dev"]
            
            # Generate spike 2-3 standard deviations away from mean
            # For firmware 1.4, spikes are more severe
            if self.firmware_version == FirmwareVersion.V1_4:
                spike_magnitude = random.uniform(2.5, 3.5) * std_dev
            else:
                spike_magnitude = random.uniform(2.0, 3.0) * std_dev
            
            # 50% chance of positive or negative spike
            if random.random() < 0.5:
                spike_value = mean + spike_magnitude
            else:
                spike_value = mean - spike_magnitude
                
            # Ensure the spike stays within sensor physical limits if defined
            min_val = normal_params.get("min", float("-inf"))
            max_val = normal_params.get("max", float("inf"))
            spike_value = max(min_val, min(spike_value, max_val))
        else:
            # Fallback to multiplicative factor if std_dev not available
            if self.firmware_version == FirmwareVersion.V1_4:
                spike_factor = random.uniform(1.8, 3.5)
            else:
                spike_factor = random.uniform(1.5, 3.0)
            
            if random.random() < 0.5:  # 50% chance of negative spike
                spike_factor = 1 / spike_factor
                
            spike_value = current_value * spike_factor
        
        modified[param.value] = spike_value

        return modified, True, AnomalyType.SPIKE

    def _apply_trend_anomaly(self, reading):
        """Apply a trend anomaly to the reading."""
        # Choose a random parameter for the trend
        params = [
            ParameterType.TEMPERATURE,
            ParameterType.HUMIDITY,
            ParameterType.VOLTAGE,
        ]
        param = random.choice(params)

        # Create a copy of the reading
        modified = reading.copy()

        # Calculate how far into the anomaly we are (0 to 1)
        start_time = self.start_times.get(AnomalyType.TREND, time.time())
        duration = self.types.get(AnomalyType.TREND.value, {}).get(
            "duration_seconds", 300
        )
        progress = min(1.0, (time.time() - start_time) / duration)

        # Apply a gradual trend (up to 50% increase/decrease)
        trend_factor = 1.0 + (0.5 * progress)
        if random.random() < 0.5:  # 50% chance of downward trend
            trend_factor = 1.0 / trend_factor

        modified[param.value] = reading[param.value] * trend_factor

        return modified, True, AnomalyType.TREND

    def _apply_pattern_anomaly(self, reading):
        """Apply a pattern anomaly to the reading."""
        # Create a copy of the reading
        modified = reading.copy()

        # Calculate how far into the anomaly we are
        start_time = self.start_times.get(AnomalyType.PATTERN, time.time())
        elapsed = time.time() - start_time

        # Apply a sinusoidal pattern to temperature
        modified[ParameterType.TEMPERATURE.value] = reading[
            ParameterType.TEMPERATURE.value
        ] * (1 + 0.2 * np.sin(elapsed / 10))

        # Apply an opposite pattern to humidity
        modified[ParameterType.HUMIDITY.value] = reading[
            ParameterType.HUMIDITY.value
        ] * (1 + 0.2 * np.sin(elapsed / 10 + np.pi))

        return modified, True, AnomalyType.PATTERN

    def _apply_missing_data_anomaly(self, reading):
        """Simulate missing data by returning None."""
        return None, True, AnomalyType.MISSING_DATA

    def _apply_noise_anomaly(self, reading):
        """Apply increased noise to all parameters."""
        # Create a copy of the reading
        modified = reading.copy()

        # Add extra noise to all parameters
        for param in [
            ParameterType.TEMPERATURE,
            ParameterType.HUMIDITY,
            ParameterType.VOLTAGE,
        ]:
            base_value = reading[param.value]

            # Firmware 1.4 has more noise
            if self.firmware_version == "1.4" or self.firmware_version == "1.4.0":
                noise_factor = 0.15  # 15% of the value as noise
            else:
                noise_factor = 0.1  # 10% of the value as noise

            # VibrationPlus sensors have more vibration noise
            if (
                param == ParameterType.HUMIDITY
                and self.manufacturer == "EnvMonitors"
            ):
                noise_factor *= 1.5

            noise = np.random.normal(0, base_value * noise_factor)
            modified[param.value] = base_value + noise

        return modified, True, AnomalyType.NOISE
    
    def update_identity(self, new_identity):
        """Update the identity configuration when it changes.
        
        Args:
            new_identity: New identity configuration
            
        Raises:
            ValueError: If any of the identity values are invalid
        """
        # Get sensor ID - handle both old and new formats
        self.id = new_identity.get("sensor_id") or new_identity.get("id")
        if not self.id:
            raise ValueError("Sensor ID is required in identity configuration")

        # Extract device info based on format
        device_info = new_identity.get("device_info", {})
        
        # Update firmware version
        firmware_val = device_info.get("firmware_version") or new_identity.get("firmware_version")
        try:
            self.firmware_version = FirmwareVersion(firmware_val)
        except ValueError:
            valid_versions = [v.value for v in FirmwareVersion]
            raise ValueError(
                f"Invalid firmware version: {firmware_val}. "
                f"Valid versions are: {valid_versions}"
            )

        # Update model
        model_val = device_info.get("model") or new_identity.get("model")
        try:
            self.model = Model(model_val)
        except ValueError:
            valid_models = [m.value for m in Model]
            raise ValueError(
                f"Invalid model: {model_val}. "
                f"Valid models are: {valid_models}"
            )

        # Update manufacturer
        manufacturer_val = device_info.get("manufacturer") or new_identity.get("manufacturer")
        if manufacturer_val:
            self.manufacturer = manufacturer_val
            raise ValueError(
                f"Invalid manufacturer: {manufacturer_val}. "
                f"Valid manufacturers are: {valid_manufacturers}"
            )

        # Update location data based on format
        location_data = new_identity.get("location")
        if isinstance(location_data, dict):
            # New nested format
            self.location = location_data.get("city") or location_data.get("address")
            coords = location_data.get("coordinates", {})
            self.latitude = coords.get("latitude", new_identity.get("latitude"))
            self.longitude = coords.get("longitude", new_identity.get("longitude"))
        else:
            # Legacy flat format
            self.location = location_data
            self.latitude = new_identity.get("latitude")
            self.longitude = new_identity.get("longitude")
            
        if not self.location:
            raise ValueError("Location is required in identity configuration")
        
        logger.info(f"Updated anomaly generator identity for sensor: {self.id}")
