#!/usr/bin/env python3
import argparse
import glob
import json
import logging
import os
import sqlite3
import time

import requests


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def collect_from_database(db_path, central_url, batch_size=100):
    """Collect data from a single database and send to central server."""
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        # Get unsynced readings
        cursor.execute(
            """
        SELECT * FROM sensor_readings 
        WHERE synced = 0
        ORDER BY timestamp ASC
        LIMIT ?
        """,
            (batch_size,),
        )

        rows = cursor.fetchall()

        if not rows:
            logging.debug(f"No new readings in {db_path}")
            return 0

        # Convert to list of dictionaries
        readings = [dict(row) for row in rows]

        # Send to central server
        response = requests.post(
            f"{central_url}/api/readings/batch",
            json={"readings": readings, "source_db": db_path},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            # Mark as synced
            reading_ids = [r["id"] for r in readings]
            placeholders = ",".join(["?"] * len(reading_ids))

            cursor.execute(
                f"""
            UPDATE sensor_readings
            SET synced = 1
            WHERE id IN ({placeholders})
            """,
                reading_ids,
            )

            conn.commit()
            logging.info(f"Synced {len(readings)} readings from {db_path}")
            return len(readings)
        else:
            logging.error(
                f"Failed to sync readings from {db_path}: {response.status_code} - {response.text}"
            )
            return 0

    except Exception as e:
        logging.error(f"Error processing {db_path}: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def scan_and_collect(data_dir, central_url, interval=60):
    """Scan for databases and collect data from each."""
    while True:
        try:
            # Find all SQLite databases
            db_files = glob.glob(f"{data_dir}/**/*.db", recursive=True)

            if not db_files:
                logging.warning(f"No database files found in {data_dir}")
            else:
                logging.info(f"Found {len(db_files)} database files")

                # Process each database
                total_synced = 0
                for db_path in db_files:
                    synced = collect_from_database(db_path, central_url)
                    total_synced += synced

                logging.info(
                    f"Sync cycle complete. Total records synced: {total_synced}"
                )

        except Exception as e:
            logging.error(f"Error in collection cycle: {e}")

        # Wait for next cycle
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Sensor Data Collector")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Directory containing sensor databases",
    )
    parser.add_argument(
        "--central-url", type=str, required=True, help="URL of central database API"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Collection interval in seconds"
    )
    args = parser.parse_args()

    setup_logging()
    logging.info(
        f"Starting collector. Scanning {args.data_dir} every {args.interval} seconds"
    )

    scan_and_collect(args.data_dir, args.central_url, args.interval)


if __name__ == "__main__":
    main()
