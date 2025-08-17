#!/usr/bin/env python3
"""
Data collector utility for aggregating sensor data from multiple databases.
This is a separate tool for collecting and centralizing data from distributed sensors.
Not required for basic sensor simulation - only needed for multi-sensor deployments.
"""
import argparse
import glob
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def collect_from_database(db_path, central_url, batch_size=100):
    """Collect data from a single database and send to central server."""
    conn = None  # Initialize conn to None
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
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


class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""
    
    def do_GET(self):
        """Handle GET requests for health status."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            health_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "collector": {
                    "running": hasattr(self.server, 'collector_running') and self.server.collector_running,
                    "last_scan": getattr(self.server, 'last_scan_time', None),
                    "total_synced": getattr(self.server, 'total_synced', 0)
                }
            }
            self.wfile.write(json.dumps(health_status).encode())
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        """Suppress request logging."""
        pass


def start_health_server(port=8081):
    """Start a simple health check HTTP server."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.collector_running = True
    server.last_scan_time = None
    server.total_synced = 0
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    logging.info(f"Health endpoint started on http://0.0.0.0:{port}/health")
    return server


def scan_and_collect(data_dir, central_url, interval=60, max_runtime=None, stop_event=None):
    """Scan for databases and collect data from each.
    
    Args:
        data_dir: Directory to scan for databases
        central_url: URL of central collection API
        interval: Sleep interval between scans
        max_runtime: Maximum runtime in seconds (None for unlimited)
        stop_event: Threading event to signal shutdown
    """
    start_time = time.time()
    cycles = 0
    
    while True:
        # Check for shutdown signal
        if stop_event and stop_event.is_set():
            logging.info("Collector received shutdown signal")
            break
            
        # Check max runtime
        if max_runtime and (time.time() - start_time) > max_runtime:
            logging.info(f"Collector reached max runtime of {max_runtime} seconds")
            break
            
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
                    # Check for shutdown during processing
                    if stop_event and stop_event.is_set():
                        break
                    synced = collect_from_database(db_path, central_url)
                    total_synced += synced

                logging.info(
                    f"Sync cycle complete. Total records synced: {total_synced}"
                )
            
            cycles += 1

        except Exception as e:
            logging.error(f"Error in collection cycle: {e}")

        # Wait for next cycle with interruptible sleep
        for _ in range(interval):
            if stop_event and stop_event.is_set():
                break
            time.sleep(1)
    
    logging.info(f"Collector stopped after {cycles} cycles")


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
    parser.add_argument(
        "--max-runtime", type=int, default=None, help="Maximum runtime in seconds"
    )
    parser.add_argument(
        "--health-port", type=int, default=8081, help="Port for health endpoint"
    )
    args = parser.parse_args()

    setup_logging()
    logging.info(
        f"Starting collector: data_dir={args.data_dir}, "
        f"central_url={args.central_url}, interval={args.interval}s"
    )
    
    # Set up shutdown handling
    stop_event = threading.Event()
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else signum
        logging.info(f"Received {sig_name} signal, shutting down gracefully...")
        stop_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start health endpoint
    health_server = None
    try:
        health_server = start_health_server(args.health_port)
    except Exception as e:
        logging.warning(f"Could not start health server: {e}")
    
    # Run collector
    try:
        scan_and_collect(
            args.data_dir, 
            args.central_url, 
            args.interval,
            max_runtime=args.max_runtime,
            stop_event=stop_event
        )
    except KeyboardInterrupt:
        logging.info("Collector interrupted by user")
    except Exception as e:
        logging.error(f"Collector error: {e}", exc_info=True)
    finally:
        if health_server:
            health_server.shutdown()
        logging.info("Collector shutdown complete")


if __name__ == "__main__":
    main()
