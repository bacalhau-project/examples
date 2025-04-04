#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pymongo"
# ]
# ///


#
# Script that transfer averaged over certain time data points to FerretDB
# Default avg window is 30s. One can override it setting env var AVG_PERIOD

import os
import sqlite3
from datetime import datetime, timedelta

from pymongo import MongoClient


def mark_data_synced(db_path, max_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        query = "UPDATE sensor_readings SET synced = 1 WHERE id <= ?"
        cursor.execute(query, (max_id,))
        conn.commit()

    except Exception as e:
        print(f"An error occurred while marking data as synced: {e}")
        return None

    finally:
        conn.close()


def get_latest_synced_timestamp(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Query to find the latest synced_at timestamp
        cursor.execute("""
            SELECT MIN(timestamp) FROM sensor_readings WHERE synced = 0;
        """)
        last_synced_timestamp = cursor.fetchone()[0]

        if last_synced_timestamp is None:
            last_synced_timestamp = datetime.min
        else:
            last_synced_timestamp = datetime.strptime(last_synced_timestamp, '%Y-%m-%dT%H:%M:%S.%f')

        return last_synced_timestamp

    except Exception as e:
        print(f"An error occurred while fetching the latest synced timestamp: {e}")
        return None

    finally:
        conn.close()


# Modifying fetch_average_data_from_sqlite to use the last_synced_timestamp
def fetch_average_data_from_sqlite(db_path, n_seconds):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get the latest synced timestamp
        last_synced_timestamp = get_latest_synced_timestamp(db_path)

        if last_synced_timestamp is None:
            print("Could not determine the last synced timestamp.")
            return []

        time_threshold = last_synced_timestamp + timedelta(seconds=n_seconds)

        # Query to fetch data for n seconds since last sync
        cursor.execute("""
            SELECT * FROM sensor_readings
            WHERE synced = 0 AND timestamp >= ? AND timestamp <= ?
        """, (last_synced_timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f'), time_threshold.strftime('%Y-%m-%dT%H:%M:%S.%f'),))

        rows = cursor.fetchall()

        if not rows:
            print("No unsynced records found.")
            return []

        # Dictionary to hold aggregated data
        sensor_data = {}
        anomaly_detected = False
        first_anomaly_type = None

        for row in rows:
            id, timestamp, sensor_id, temperature, vibration, voltage, status_code, anomaly_flag, anomaly_type, firmware_version, model, manufacturer, location, synced = row

            if anomaly_flag == 1 and not anomaly_detected:
                anomaly_detected = True
                first_anomaly_type = anomaly_type

            if sensor_id not in sensor_data:
                sensor_data[sensor_id] = {
                    'count': 0,
                    'temperature_sum': 0,
                    'vibration_sum': 0,
                    'voltage_sum': 0
                }

            sensor_data[sensor_id]['count'] += 1
            sensor_data[sensor_id]['temperature_sum'] += temperature
            sensor_data[sensor_id]['vibration_sum'] += vibration
            sensor_data[sensor_id]['voltage_sum'] += voltage

        # Calculate averages and prepare final data
        averaged_data = []
        for sensor_id, data in sensor_data.items():
            avg_temperature = data['temperature_sum'] / data['count']
            avg_vibration = data['vibration_sum'] / data['count']
            avg_voltage = data['voltage_sum'] / data['count']

            # Use the time_threshold as the timestamp here
            avg_row = {
                'id': id,
                'timestamp': time_threshold.strftime('%Y-%m-%d %H:%M:%S'),
                'sensor_id': sensor_id,
                'temperature': avg_temperature,
                'vibration': avg_vibration,
                'voltage': avg_voltage,
                'status_code': status_code,
                'anomaly_flag': anomaly_detected,
                'anomaly_type': first_anomaly_type,
                'firmware_version': firmware_version,
                'model': model,
                'manufacturer': manufacturer,
                'location': location,
                'synced': 0,
            }

            averaged_data.append(avg_row)
        return averaged_data

    except Exception as e:
        print(f"An error occurred while fetching and processing data: {e}")
        return []

    finally:
        conn.close()


# insert_into_mongodb remains unchanged
def insert_into_mongodb(averaged_data):
    # Retrieve MongoDB connection details from environment variables
    mongodb_uri = os.getenv("MONGODB_URI", "")
    database_name = os.getenv("DATABASE_NAME", "postgres")
    collection_name = os.getenv("COLLECTION_NAME", "sensor_readings")

    try:
        # Connect to the MongoDB client
        client = MongoClient(mongodb_uri)
        db = client[database_name]
        collection = db[collection_name]
        if averaged_data:
            result = collection.insert_many(averaged_data)
            print(f"Inserted {len(result.inserted_ids)} records into MongoDB.")
        else:
            print("No data to insert.")

    except Exception as e:
        print(f"An error occurred while inserting data: {e}")

    finally:
        client.close()

    return averaged_data[-1]["id"]


if __name__ == "__main__":
    db_path = "/app/data/sensor_data.db"
    n_seconds = int(os.getenv("AVG_PERIOD", 30))

    # Get the latest synced timestamp
    last_synced_timestamp = get_latest_synced_timestamp(db_path)

    elapsed_time = (datetime.now() - last_synced_timestamp).total_seconds()

    # Exit if n_seconds have not passed
    if elapsed_time < n_seconds:
        print(f"Exiting: Less than {n_seconds} seconds have passed since the last sync.")
    else:
        averaged_data = fetch_average_data_from_sqlite(db_path, n_seconds=n_seconds)
        if averaged_data:
            last_id = insert_into_mongodb(averaged_data)
            mark_data_synced(db_path, last_id)
