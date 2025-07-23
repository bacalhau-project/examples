import pytest

from src.enums import AnomalyType, ParameterType


class TestEnums:
    # Manufacturer enum tests removed - any string is now accepted for manufacturer

    def test_anomaly_type_enum_values(self):
        """Test that AnomalyType enum has expected values."""
        assert AnomalyType.SPIKE.value == "spike"
        assert AnomalyType.TREND.value == "trend"
        assert AnomalyType.PATTERN.value == "pattern"
        assert AnomalyType.MISSING_DATA.value == "missing_data"
        assert AnomalyType.NOISE.value == "noise"

    def test_anomaly_type_enum_creation_from_value(self):
        """Test creating AnomalyType enum from string values."""
        assert AnomalyType("spike") == AnomalyType.SPIKE
        assert AnomalyType("trend") == AnomalyType.TREND
        assert AnomalyType("pattern") == AnomalyType.PATTERN
        assert AnomalyType("missing_data") == AnomalyType.MISSING_DATA
        assert AnomalyType("noise") == AnomalyType.NOISE

    def test_parameter_type_enum_values(self):
        """Test that ParameterType enum has expected values."""
        assert ParameterType.TEMPERATURE.value == "temperature"
        assert ParameterType.HUMIDITY.value == "humidity"
        assert ParameterType.PRESSURE.value == "pressure"
        assert ParameterType.VOLTAGE.value == "voltage"

    def test_parameter_type_enum_creation_from_value(self):
        """Test creating ParameterType enum from string values."""
        assert ParameterType("temperature") == ParameterType.TEMPERATURE
        assert ParameterType("humidity") == ParameterType.HUMIDITY
        assert ParameterType("pressure") == ParameterType.PRESSURE
        assert ParameterType("voltage") == ParameterType.VOLTAGE

    def test_all_enums_are_unique(self):
        """Test that all enum values are unique within each enum."""

        # Test AnomalyType values are unique
        anomaly_values = [a.value for a in AnomalyType]
        assert len(anomaly_values) == len(set(anomaly_values))

        # Test ParameterType values are unique
        parameter_values = [p.value for p in ParameterType]
        assert len(parameter_values) == len(set(parameter_values))

    def test_enum_iteration(self):
        """Test that enums can be iterated over."""
        # Manufacturer enum tests removed - any string is now accepted

        anomaly_types = list(AnomalyType)
        assert len(anomaly_types) == 5
        assert AnomalyType.SPIKE in anomaly_types

        parameter_types = list(ParameterType)
        assert len(parameter_types) == 4
        assert ParameterType.TEMPERATURE in parameter_types