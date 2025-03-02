import logging
import random
import time
from enum import Enum

import numpy as np


class AnomalyType(Enum):
    SPIKE = "spike"
    TREND = "trend"
    PATTERN = "pattern"
    MISSING_DATA = "missing_data"
    NOISE = "noise"


class AnomalyGenerator:
    def __init__(self, config, sensor_config):
        """Initialize the anomaly generator with configuration.

        Args:
            config: Anomaly configuration
            sensor_config: Sensor identity configuration
        """
        self.config = config
        self.sensor_config = sensor_config
        self.enabled = config.get("enabled", True)
        self.probability = config.get("probability", 0.05)
        self.types = config.get("types", {})

        # Get firmware version
        self.firmware_version = sensor_config.get("firmware_version", "1.3")
        self.model = sensor_config.get("model", "TempVibe-2000")
        self.manufacturer = sensor_config.get("manufacturer", "SensorTech")
        self.location = sensor_config.get("location", "Factory A - Machine 1")

        # Track active anomalies
        self.active_anomalies = {}
        self.start_times = {}

        # Log sensor identity
        logging.info(
            f"Initializing anomaly generator for sensor: {sensor_config.get('id', 'unknown')}"
        )
        logging.info(f"  Firmware: {self.firmware_version}")
        logging.info(f"  Model: {self.model}")
        logging.info(f"  Manufacturer: {self.manufacturer}")
        logging.info(f"  Location: {self.location}")

    def should_generate_anomaly(self):
        """Determine if an anomaly should be generated based on probability and firmware version."""
        if not self.enabled:
            return False

        # Adjust probability based on firmware version
        adjusted_probability = self.probability

        # Firmware 1.3 has higher anomaly probability
        if self.firmware_version == "1.3":
            adjusted_probability *= 1.5  # 50% more anomalies

        # Firmware 1.4 has lower anomaly probability
        elif self.firmware_version == "1.4":
            adjusted_probability *= 0.7  # 30% fewer anomalies

        # Adjust based on manufacturer
        if self.manufacturer == "SensorTech":
            # Standard probability
            pass
        elif self.manufacturer == "DataSense":
            adjusted_probability *= 0.8  # 20% fewer anomalies but more severe
        elif self.manufacturer == "VibrationPlus":
            adjusted_probability *= 1.2  # 20% more anomalies

        return random.random() < adjusted_probability

    def select_anomaly_type(self):
        """Select an anomaly type based on configured weights and sensor characteristics."""
        # Filter enabled anomaly types
        enabled_types = {}
        for anomaly_type, config in self.types.items():
            if config.get("enabled", True):
                enabled_types[anomaly_type] = config.get("weight", 1.0)

        if not enabled_types:
            return None

        # Adjust weights based on model
        if self.model == "TempVibe-1000":
            # More prone to missing data
            if "missing_data" in enabled_types:
                enabled_types["missing_data"] *= 2.0
        elif self.model == "TempVibe-2000":
            # More prone to pattern anomalies
            if "pattern" in enabled_types:
                enabled_types["pattern"] *= 1.5
        elif self.model == "TempVibe-3000":
            # More prone to spike anomalies
            if "spike" in enabled_types:
                enabled_types["spike"] *= 1.5

        # Adjust weights based on firmware
        if self.firmware_version == "1.3":
            # More temperature spikes and noise
            if "spike" in enabled_types:
                enabled_types["spike"] *= 1.3
            if "noise" in enabled_types:
                enabled_types["noise"] *= 1.5
        elif self.firmware_version == "1.4":
            # Fewer spikes, more stable
            if "spike" in enabled_types:
                enabled_types["spike"] *= 0.7
            if "noise" in enabled_types:
                enabled_types["noise"] *= 0.8

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
        logging.info(f"Started {anomaly_type} anomaly")

    def is_anomaly_active(self, anomaly_type):
        """Check if an anomaly is currently active."""
        if (
            anomaly_type not in self.active_anomalies
            or not self.active_anomalies[anomaly_type]
        ):
            return False

        # Check if the anomaly duration has expired
        start_time = self.start_times.get(anomaly_type, 0)
        duration = self.types.get(anomaly_type, {}).get("duration_seconds", 60)

        if time.time() - start_time > duration:
            self.active_anomalies[anomaly_type] = False
            logging.info(f"Ended {anomaly_type} anomaly")
            return False

        return True

    def apply_anomaly(self, reading, anomaly_type):
        """Apply the specified anomaly to the sensor reading."""
        if anomaly_type == AnomalyType.SPIKE.value:
            return self._apply_spike_anomaly(reading)
        elif anomaly_type == AnomalyType.TREND.value:
            return self._apply_trend_anomaly(reading)
        elif anomaly_type == AnomalyType.PATTERN.value:
            return self._apply_pattern_anomaly(reading)
        elif anomaly_type == AnomalyType.MISSING_DATA.value:
            return self._apply_missing_data_anomaly(reading)
        elif anomaly_type == AnomalyType.NOISE.value:
            return self._apply_noise_anomaly(reading)
        else:
            return reading, False, None

    def _apply_spike_anomaly(self, reading):
        """Apply a spike anomaly to the reading."""
        # Choose a random parameter to spike
        params = ["temperature", "vibration", "voltage"]

        # For firmware 1.3, temperature spikes are more common
        if self.firmware_version == "1.3":
            if random.random() < 0.6:  # 60% chance to choose temperature
                param = "temperature"
            else:
                param = random.choice(["vibration", "voltage"])
        else:
            param = random.choice(params)

        # Create a copy of the reading
        modified = reading.copy()

        # Apply a spike (multiply by a factor between 1.5 and 3)
        # For firmware 1.3, spikes are more severe
        if self.firmware_version == "1.3":
            spike_factor = random.uniform(1.8, 3.5)
        else:
            spike_factor = random.uniform(1.5, 3.0)

        if random.random() < 0.5:  # 50% chance of negative spike
            spike_factor = 1 / spike_factor

        modified[param] = reading[param] * spike_factor

        return modified, True, AnomalyType.SPIKE.value

    def _apply_trend_anomaly(self, reading):
        """Apply a trend anomaly to the reading."""
        # Choose a random parameter for the trend
        params = ["temperature", "vibration", "voltage"]
        param = random.choice(params)

        # Create a copy of the reading
        modified = reading.copy()

        # Calculate how far into the anomaly we are (0 to 1)
        start_time = self.start_times.get(AnomalyType.TREND.value, time.time())
        duration = self.types.get(AnomalyType.TREND.value, {}).get(
            "duration_seconds", 300
        )
        progress = min(1.0, (time.time() - start_time) / duration)

        # Apply a gradual trend (up to 50% increase/decrease)
        trend_factor = 1.0 + (0.5 * progress)
        if random.random() < 0.5:  # 50% chance of downward trend
            trend_factor = 1.0 / trend_factor

        modified[param] = reading[param] * trend_factor

        return modified, True, AnomalyType.TREND.value

    def _apply_pattern_anomaly(self, reading):
        """Apply a pattern anomaly to the reading."""
        # Create a copy of the reading
        modified = reading.copy()

        # Calculate how far into the anomaly we are
        start_time = self.start_times.get(AnomalyType.PATTERN.value, time.time())
        elapsed = time.time() - start_time

        # Apply a sinusoidal pattern to temperature
        modified["temperature"] = reading["temperature"] * (
            1 + 0.2 * np.sin(elapsed / 10)
        )

        # Apply an opposite pattern to vibration
        modified["vibration"] = reading["vibration"] * (
            1 + 0.2 * np.sin(elapsed / 10 + np.pi)
        )

        return modified, True, AnomalyType.PATTERN.value

    def _apply_missing_data_anomaly(self, reading):
        """Simulate missing data by returning None."""
        return None, True, AnomalyType.MISSING_DATA.value

    def _apply_noise_anomaly(self, reading):
        """Apply increased noise to all parameters."""
        # Create a copy of the reading
        modified = reading.copy()

        # Add extra noise to all parameters
        for param in ["temperature", "vibration", "voltage"]:
            base_value = reading[param]

            # Firmware 1.3 has more noise
            if self.firmware_version == "1.3":
                noise_factor = 0.15  # 15% of the value as noise
            else:
                noise_factor = 0.1  # 10% of the value as noise

            # VibrationPlus sensors have more vibration noise
            if param == "vibration" and self.manufacturer == "VibrationPlus":
                noise_factor *= 1.5

            noise = np.random.normal(0, base_value * noise_factor)
            modified[param] = base_value + noise

        return modified, True, AnomalyType.NOISE.value
