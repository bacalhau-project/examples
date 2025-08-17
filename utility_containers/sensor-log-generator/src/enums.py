from enum import Enum


class Manufacturer(Enum):
    SENSORTECH = "SensorTech"
    ENVMONITORS = "EnvMonitors"
    IOTPRO = "IoTPro"
    DATALOGGER = "DataLogger"


class FirmwareVersion(Enum):
    V1_3 = "1.3.0"
    V1_4 = "1.4.0"
    V1_5 = "1.5.0"
    V2_0 = "2.0.0"


class Model(Enum):
    TEMPSENSOR_PRO = "TempSensor Pro"
    WEATHERSTATION_PRO = "WeatherStation Pro"
    ENVMONITOR_2000 = "EnvMonitor 2000"
    AIRDATA_PLUS = "AirData-Plus"


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
