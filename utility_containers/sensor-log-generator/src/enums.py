from enum import Enum


class Manufacturer(Enum):
    SENSORTECH = "SensorTech"
    ENVMONITORS = "EnvMonitors"
    IOTPRO = "IoTPro"


class Model(Enum):
    ENVMONITOR_3000 = "EnvMonitor-3000"
    ENVMONITOR_4000 = "EnvMonitor-4000"
    ENVMONITOR_5000 = "EnvMonitor-5000"


class FirmwareVersion(Enum):
    V1_4 = "1.4"
    V1_5 = "1.5"
    V2_0 = "2.0"


class AnomalyType(Enum):
    SPIKE = "spike"
    TREND = "trend"
    PATTERN = "pattern"
    MISSING_DATA = "missing_data"
    NOISE = "noise"


class ParameterType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    VOLTAGE = "voltage"
