import logging
import random
import time
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from .enums import AnomalyType, FirmwareVersion, Manufacturer, Model, ParameterType

logger = logging.getLogger(__name__)


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

        # Get firmware version
        self.id = identity.get("id")
        if not self.id:
            raise ValueError("Sensor ID is required in identity configuration")

        # Initialize identity with validation
        try:
            self.firmware_version = FirmwareVersion(identity.get("firmware_version"))
        except ValueError:
            valid_versions = [v.value for v in FirmwareVersion]
            raise ValueError(
                f"Invalid firmware version: {identity.get('firmware_version')}. "
                f"Valid versions are: {valid_versions}"
            )

        try:
            self.model = Model(identity.get("model"))
        except ValueError:
            valid_models = [m.value for m in Model]
            raise ValueError(
                f"Invalid model: {identity.get('model')}. "
                f"Valid models are: {valid_models}"
            )

        try:
            self.manufacturer = Manufacturer(identity.get("manufacturer"))
        except ValueError:
            valid_manufacturers = [m.value for m in Manufacturer]
            raise ValueError(
                f"Invalid manufacturer: {identity.get('manufacturer')}. "
                f"Valid manufacturers are: {valid_manufacturers}"
            )

        self.location = identity.get("location")
        self.latitude = identity.get("latitude")
        self.longitude = identity.get("longitude")
        if not self.location:
            raise ValueError("Location is required in identity configuration")

        # Track active anomalies
        self.active_anomalies = {}
        self.start_times = {}

        # Log sensor identity
        logger.info(f"Initializing anomaly generator for sensor: {self.id}")
        logger.info(f"  Firmware: {self.firmware_version.value}")
        logger.info(f"  Model: {self.model.value}")
        logger.info(f"  Manufacturer: {self.manufacturer.value}")
        logger.info(f"  Location: {self.location}")
        logger.info(f"  Latitude: {self.latitude}")
        logger.info(f"  Longitude: {self.longitude}")

    def should_generate_anomaly(self):
        """Determine if an anomaly should be generated based on probability and firmware version."""
        if not self.enabled:
            return False

        # Adjust probability based on firmware version
        adjusted_probability = self.probability

        # Firmware 1.3 has higher anomaly probability
        if self.firmware_version == FirmwareVersion.V1_4:
            adjusted_probability *= 1.5  # 50% more anomalies

        # Firmware 1.4 has lower anomaly probability
        elif self.firmware_version == FirmwareVersion.V1_5:
            adjusted_probability *= 0.7  # 30% fewer anomalies

        # Adjust based on manufacturer
        if self.manufacturer == Manufacturer.SENSORTECH:
            # Standard probability
            pass
        elif self.manufacturer == Manufacturer.ENVMONITORS:
            adjusted_probability *= 0.8  # 20% fewer anomalies but more severe
        elif self.manufacturer == Manufacturer.IOTPRO:
            adjusted_probability *= 1.2  # 20% more anomalies

        return random.random() < adjusted_probability

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
        if self.model == Model.ENVMONITOR_3000:
            # More prone to missing data
            if AnomalyType.MISSING_DATA in enabled_types:
                enabled_types[AnomalyType.MISSING_DATA] *= 2.0
        elif self.model == Model.ENVMONITOR_4000:
            # More prone to pattern anomalies
            if AnomalyType.PATTERN in enabled_types:
                enabled_types[AnomalyType.PATTERN] *= 1.5
        elif self.model == Model.ENVMONITOR_5000:
            # More prone to spike anomalies
            if AnomalyType.SPIKE in enabled_types:
                enabled_types[AnomalyType.SPIKE] *= 1.5

        # Adjust weights based on firmware
        if self.firmware_version == FirmwareVersion.V1_4:
            # More temperature spikes and noise
            if AnomalyType.SPIKE in enabled_types:
                enabled_types[AnomalyType.SPIKE] *= 1.3
            if AnomalyType.NOISE in enabled_types:
                enabled_types[AnomalyType.NOISE] *= 1.5
        elif self.firmware_version == FirmwareVersion.V1_5:
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

        # Apply a spike (multiply by a factor between 1.5 and 3)
        # For firmware 1.3, spikes are more severe
        if self.firmware_version == FirmwareVersion.V1_4:
            spike_factor = random.uniform(1.8, 3.5)
        else:
            spike_factor = random.uniform(1.5, 3.0)

        if random.random() < 0.5:  # 50% chance of negative spike
            spike_factor = 1 / spike_factor

        modified[param.value] = reading[param.value] * spike_factor

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

            # Firmware 1.3 has more noise
            if self.firmware_version == FirmwareVersion.V1_4:
                noise_factor = 0.15  # 15% of the value as noise
            else:
                noise_factor = 0.1  # 10% of the value as noise

            # VibrationPlus sensors have more vibration noise
            if (
                param == ParameterType.HUMIDITY
                and self.manufacturer == Manufacturer.ENVMONITORS
            ):
                noise_factor *= 1.5

            noise = np.random.normal(0, base_value * noise_factor)
            modified[param.value] = base_value + noise

        return modified, True, AnomalyType.NOISE
