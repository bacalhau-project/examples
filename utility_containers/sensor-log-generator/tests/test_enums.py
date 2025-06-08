import pytest

from src.enums import AnomalyType, FirmwareVersion, Manufacturer, Model, ParameterType


class TestEnums:
    def test_manufacturer_enum_values(self):
        """Test that Manufacturer enum has expected values."""
        assert Manufacturer.SENSORTECH.value == "SensorTech"
        assert Manufacturer.ENVMONITORS.value == "EnvMonitors"
        assert Manufacturer.IOTPRO.value == "IoTPro"

    def test_manufacturer_enum_creation_from_value(self):
        """Test creating Manufacturer enum from string values."""
        assert Manufacturer("SensorTech") == Manufacturer.SENSORTECH
        assert Manufacturer("EnvMonitors") == Manufacturer.ENVMONITORS
        assert Manufacturer("IoTPro") == Manufacturer.IOTPRO

    def test_manufacturer_enum_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            Manufacturer("InvalidManufacturer")

    def test_model_enum_values(self):
        """Test that Model enum has expected values."""
        assert Model.ENVMONITOR_3000.value == "EnvMonitor-3000"
        assert Model.ENVMONITOR_4000.value == "EnvMonitor-4000"
        assert Model.ENVMONITOR_5000.value == "EnvMonitor-5000"

    def test_model_enum_creation_from_value(self):
        """Test creating Model enum from string values."""
        assert Model("EnvMonitor-3000") == Model.ENVMONITOR_3000
        assert Model("EnvMonitor-4000") == Model.ENVMONITOR_4000
        assert Model("EnvMonitor-5000") == Model.ENVMONITOR_5000

    def test_firmware_version_enum_values(self):
        """Test that FirmwareVersion enum has expected values."""
        assert FirmwareVersion.V1_4.value == "1.4"
        assert FirmwareVersion.V1_5.value == "1.5"
        assert FirmwareVersion.V2_0.value == "2.0"

    def test_firmware_version_enum_creation_from_value(self):
        """Test creating FirmwareVersion enum from string values."""
        assert FirmwareVersion("1.4") == FirmwareVersion.V1_4
        assert FirmwareVersion("1.5") == FirmwareVersion.V1_5
        assert FirmwareVersion("2.0") == FirmwareVersion.V2_0

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
        # Test Manufacturer values are unique
        manufacturer_values = [m.value for m in Manufacturer]
        assert len(manufacturer_values) == len(set(manufacturer_values))

        # Test Model values are unique
        model_values = [m.value for m in Model]
        assert len(model_values) == len(set(model_values))

        # Test FirmwareVersion values are unique
        firmware_values = [f.value for f in FirmwareVersion]
        assert len(firmware_values) == len(set(firmware_values))

        # Test AnomalyType values are unique
        anomaly_values = [a.value for a in AnomalyType]
        assert len(anomaly_values) == len(set(anomaly_values))

        # Test ParameterType values are unique
        parameter_values = [p.value for p in ParameterType]
        assert len(parameter_values) == len(set(parameter_values))

    def test_enum_iteration(self):
        """Test that enums can be iterated over."""
        manufacturers = list(Manufacturer)
        assert len(manufacturers) == 3
        assert Manufacturer.SENSORTECH in manufacturers

        models = list(Model)
        assert len(models) == 3
        assert Model.ENVMONITOR_3000 in models

        firmware_versions = list(FirmwareVersion)
        assert len(firmware_versions) == 3
        assert FirmwareVersion.V1_4 in firmware_versions

        anomaly_types = list(AnomalyType)
        assert len(anomaly_types) == 5
        assert AnomalyType.SPIKE in anomaly_types

        parameter_types = list(ParameterType)
        assert len(parameter_types) == 4
        assert ParameterType.TEMPERATURE in parameter_types