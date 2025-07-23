from enum import Enum


class Manufacturer(Enum):
    SENSORTECH = "SensorTech"
    ENVMONITORS = "EnvMonitors"
    IOTPRO = "IoTPro"
    DATALOGGER = "DataLogger"


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
