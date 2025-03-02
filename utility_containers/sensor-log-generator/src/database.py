import logging
import os
import sqlite3
from datetime import datetime

import requests


class SensorDatabase:
    def __init__(self, db_path="sensor_data.db"):
        """Initialize the database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Establish connection to the SQLite database."""
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")

            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logging.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise
        except Exception as e:
            logging.error(f"Error setting up database: {e}")
            raise

    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        try:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                temperature REAL,
                vibration REAL,
                voltage REAL,
                status_code INTEGER,
                anomaly_flag BOOLEAN,
                anomaly_type TEXT,
                firmware_version TEXT,
                model TEXT,
                manufacturer TEXT,
                location TEXT
            )
            """)

            # Create index on timestamp for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON sensor_readings (timestamp)
            """)

            # Create index on sensor_id for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_id 
            ON sensor_readings (sensor_id)
            """)

            # Create index on firmware_version for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_firmware 
            ON sensor_readings (firmware_version)
            """)

            self.conn.commit()
            logging.info("Database tables created successfully")
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
            raise

    def insert_reading(
        self,
        sensor_id,
        temperature,
        vibration,
        voltage,
        status_code,
        anomaly_flag=False,
        anomaly_type=None,
        firmware_version=None,
        model=None,
        manufacturer=None,
        location=None,
    ):
        """Insert a new sensor reading into the database."""
        try:
            timestamp = datetime.now().isoformat()
            self.cursor.execute(
                """
            INSERT INTO sensor_readings 
            (timestamp, sensor_id, temperature, vibration, voltage, 
             status_code, anomaly_flag, anomaly_type, firmware_version,
             model, manufacturer, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    sensor_id,
                    temperature,
                    vibration,
                    voltage,
                    status_code,
                    anomaly_flag,
                    anomaly_type,
                    firmware_version,
                    model,
                    manufacturer,
                    location,
                ),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error inserting reading: {e}")
            self.conn.rollback()
            raise

    def get_readings(self, limit=100, sensor_id=None):
        """Retrieve sensor readings from the database."""
        try:
            query = "SELECT * FROM sensor_readings"
            params = []

            if sensor_id:
                query += " WHERE sensor_id = ?"
                params.append(sensor_id)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error retrieving readings: {e}")
            raise

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed")

    def sync_to_central_db(self, central_db_url, batch_size=100):
        """Sync recent readings to a central database."""
        try:
            # Get recent unsynced readings
            self.cursor.execute(
                """
            SELECT * FROM sensor_readings 
            WHERE synced = 0
            ORDER BY timestamp ASC
            LIMIT ?
            """,
                (batch_size,),
            )

            readings = self.cursor.fetchall()

            if not readings:
                logging.info("No new readings to sync")
                return 0

            # Push to central database
            response = requests.post(
                f"{central_db_url}/api/readings/batch",
                json={"readings": readings},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                # Mark as synced
                reading_ids = [r[0] for r in readings]  # Assuming id is first column
                placeholders = ",".join(["?"] * len(reading_ids))

                self.cursor.execute(
                    f"""
                UPDATE sensor_readings
                SET synced = 1
                WHERE id IN ({placeholders})
                """,
                    reading_ids,
                )

                self.conn.commit()
                logging.info(f"Synced {len(readings)} readings to central database")
                return len(readings)
            else:
                logging.error(
                    f"Failed to sync readings: {response.status_code} - {response.text}"
                )
                return 0

        except Exception as e:
            logging.error(f"Error syncing to central database: {e}")
            return 0
