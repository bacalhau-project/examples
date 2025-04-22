# Sensor Data Architecture

This document explains how sensor data flows through the system and how archives are organized.

## Data Flow Overview

1. **Sensor Containers**: Generate sensor readings
   - Each sensor has a unique ID: `{CITY}_{SENSOR_CODE}`
   - Data is stored in SQLite databases in city/sensor-specific directories

2. **Uploader Containers**: Process sensor data
   - Each city has a dedicated uploader
   - Reads data from SQLite databases in city folders
   - Uploads to Cosmos DB
   - Archives processed data to parquet files

## Directory Structure

```
/
├── data/
│   ├── London/
│   │   ├── abc123/
│   │   │   └── sensor_data.db
│   │   ├── def456/
│   │   │   └── sensor_data.db
│   │   └── ...
│   ├── Paris/
│   │   └── ...
│   └── ...
├── archive/
│   ├── London/
│   │   ├── abc123.parquet
│   │   ├── def456.parquet
│   │   └── ...
│   ├── Paris/
│   │   └── ...
│   └── ...
└── ...
```

## Archive Structure

- **City-based organization**: Archives are organized by city directories
- **Sensor-based filenames**: Within each city directory, files are named by sensor code (the unique part of sensor ID)
- **Data consolidation**: Parquet files merge data over time, preserving historical records

## Implementation Notes

1. **Docker Compose**:
   - Mounts city-specific data directories
   - Maps city-specific archive directories
   - Each uploader only has access to its city's data

2. **Data Identification**:
   - Sensors store their location and ID in the database
   - If database fields are empty, data is derived from directory structure
   - This fallback ensures data integrity even with incomplete database records

## Troubleshooting

If you see sensor data in the wrong city directory or with incorrect naming:

1. Check that sensor IDs are properly set in environment variables
2. Verify SQLite databases have proper sensor_id and location fields
3. Check Docker Compose volume mappings match expected structure

The uploader is designed to handle a variety of edge cases to ensure data is preserved even when metadata is inconsistent.