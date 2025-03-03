import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class MonitoringRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the monitoring server."""

    # Class variable to store reference to simulator
    simulator = None

    def log_message(self, format, *args):
        """Override to use the application's logger instead of stderr."""
        logging.info(f"Monitor server: {format % args}")

    def _send_response(self, status_code, content_type, content):
        """Helper method to send a response with the given status code and content."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
        self.end_headers()

        if isinstance(content, str):
            content = content.encode("utf-8")
        self.wfile.write(content)

    def _send_json_response(self, status_code, data):
        """Helper method to send a JSON response."""
        self._send_response(status_code, "application/json", json.dumps(data, indent=2))

    def _handle_health(self):
        """Handle health check requests."""
        if not self.simulator:
            self._send_json_response(
                503, {"status": "error", "message": "Simulator not initialized"}
            )
            return

        # Check database health
        db_healthy = (
            self.simulator.db.is_healthy() if hasattr(self.simulator, "db") else False
        )

        # Overall health status
        is_healthy = self.simulator.running and db_healthy

        health_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "simulator_running": self.simulator.running,
            "database_healthy": db_healthy,
            "timestamp": time.time(),
        }

        status_code = 200 if is_healthy else 503
        self._send_json_response(status_code, health_data)

    def _handle_metrics(self):
        """Handle metrics requests."""
        if not self.simulator:
            self._send_json_response(
                503, {"status": "error", "message": "Simulator not initialized"}
            )
            return

        # Get simulator status
        simulator_status = self.simulator.get_status()

        # Get database performance metrics
        db_metrics = {}
        if hasattr(self.simulator, "db") and hasattr(
            self.simulator.db, "get_performance_stats"
        ):
            db_metrics = self.simulator.db.get_performance_stats()

        # Get sync stats
        sync_stats = {}
        if hasattr(self.simulator, "db") and hasattr(
            self.simulator.db, "get_sync_stats"
        ):
            sync_stats = self.simulator.db.get_sync_stats()

        # Combine all metrics
        metrics = {
            "simulator": simulator_status,
            "database": db_metrics,
            "sync": sync_stats,
            "timestamp": time.time(),
        }

        self._send_json_response(200, metrics)

    def _handle_status(self):
        """Handle status requests."""
        if not self.simulator:
            self._send_json_response(
                503, {"status": "error", "message": "Simulator not initialized"}
            )
            return

        status = self.simulator.get_status()
        self._send_json_response(200, status)

    def _handle_prometheus(self):
        """Handle Prometheus metrics requests."""
        if not self.simulator:
            self._send_response(503, "text/plain", "# ERROR: Simulator not initialized")
            return

        # Get metrics data
        simulator_status = self.simulator.get_status()
        db_metrics = {}
        if hasattr(self.simulator, "db") and hasattr(
            self.simulator.db, "get_performance_stats"
        ):
            db_metrics = self.simulator.db.get_performance_stats()

        sync_stats = {}
        if hasattr(self.simulator, "db") and hasattr(
            self.simulator.db, "get_sync_stats"
        ):
            sync_stats = self.simulator.db.get_sync_stats()

        # Format as Prometheus metrics
        lines = []

        # Simulator metrics
        lines.append(
            "# HELP sensor_simulator_running Whether the simulator is running (1=yes, 0=no)"
        )
        lines.append("# TYPE sensor_simulator_running gauge")
        lines.append(
            f"sensor_simulator_running {1 if simulator_status.get('running', False) else 0}"
        )

        lines.append(
            "# HELP sensor_simulator_readings_total Total number of readings generated"
        )
        lines.append("# TYPE sensor_simulator_readings_total counter")
        lines.append(
            f"sensor_simulator_readings_total {simulator_status.get('readings_count', 0)}"
        )

        lines.append(
            "# HELP sensor_simulator_errors_total Total number of errors encountered"
        )
        lines.append("# TYPE sensor_simulator_errors_total counter")
        lines.append(
            f"sensor_simulator_errors_total {simulator_status.get('error_count', 0)}"
        )

        lines.append("# HELP sensor_simulator_elapsed_seconds Elapsed time in seconds")
        lines.append("# TYPE sensor_simulator_elapsed_seconds gauge")
        lines.append(
            f"sensor_simulator_elapsed_seconds {simulator_status.get('elapsed_seconds', 0)}"
        )

        # Database metrics
        if db_metrics:
            lines.append(
                "# HELP sensor_database_readings_total Total number of readings in the database"
            )
            lines.append("# TYPE sensor_database_readings_total counter")
            lines.append(
                f"sensor_database_readings_total {db_metrics.get('total_readings', 0)}"
            )

            lines.append(
                "# HELP sensor_database_batches_total Total number of batch inserts"
            )
            lines.append("# TYPE sensor_database_batches_total counter")
            lines.append(
                f"sensor_database_batches_total {db_metrics.get('total_batches', 0)}"
            )

            lines.append(
                "# HELP sensor_database_avg_insert_time_ms Average insert time in milliseconds"
            )
            lines.append("# TYPE sensor_database_avg_insert_time_ms gauge")
            lines.append(
                f"sensor_database_avg_insert_time_ms {db_metrics.get('avg_insert_time_ms', 0)}"
            )

            lines.append("# HELP sensor_database_size_bytes Database size in bytes")
            lines.append("# TYPE sensor_database_size_bytes gauge")
            lines.append(
                f"sensor_database_size_bytes {db_metrics.get('database_size_bytes', 0)}"
            )

        # Sync metrics
        if sync_stats:
            lines.append("# HELP sensor_sync_total_readings Total number of readings")
            lines.append("# TYPE sensor_sync_total_readings gauge")
            lines.append(
                f"sensor_sync_total_readings {sync_stats.get('total_readings', 0)}"
            )

            lines.append("# HELP sensor_sync_synced_readings Number of synced readings")
            lines.append("# TYPE sensor_sync_synced_readings gauge")
            lines.append(
                f"sensor_sync_synced_readings {sync_stats.get('synced_readings', 0)}"
            )

            lines.append(
                "# HELP sensor_sync_unsynced_readings Number of unsynced readings"
            )
            lines.append("# TYPE sensor_sync_unsynced_readings gauge")
            lines.append(
                f"sensor_sync_unsynced_readings {sync_stats.get('unsynced_readings', 0)}"
            )

            lines.append(
                "# HELP sensor_sync_percentage Percentage of readings that are synced"
            )
            lines.append("# TYPE sensor_sync_percentage gauge")
            lines.append(
                f"sensor_sync_percentage {sync_stats.get('sync_percentage', 0)}"
            )

        self._send_response(200, "text/plain", "\n".join(lines))

    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Route to appropriate handler based on path
        if path == "/health" or path == "/healthz":
            self._handle_health()
        elif path == "/metrics":
            self._handle_metrics()
        elif path == "/status":
            self._handle_status()
        elif path == "/prometheus":
            self._handle_prometheus()
        else:
            # Default to showing available endpoints
            endpoints = {
                "endpoints": {
                    "/health": "Health check endpoint",
                    "/metrics": "JSON metrics endpoint",
                    "/status": "Simulator status endpoint",
                    "/prometheus": "Prometheus metrics endpoint",
                },
                "simulator_running": self.simulator.running
                if self.simulator
                else False,
            }
            self._send_json_response(200, endpoints)


class MonitoringServer:
    """HTTP server for monitoring the sensor simulator."""

    def __init__(self, simulator, host="0.0.0.0", port=8080):
        """Initialize the monitoring server.

        Args:
            simulator: Reference to the SensorSimulator instance
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.simulator = simulator
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False

        # Set the simulator reference in the request handler
        MonitoringRequestHandler.simulator = simulator

    def start(self):
        """Start the monitoring server in a background thread."""
        if self.running:
            logging.warning("Monitoring server is already running")
            return

        try:
            self.server = HTTPServer((self.host, self.port), MonitoringRequestHandler)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            self.running = True
            logging.info(f"Monitoring server started on http://{self.host}:{self.port}")
        except Exception as e:
            logging.error(f"Failed to start monitoring server: {e}")

    def _run_server(self):
        """Run the HTTP server."""
        try:
            self.server.serve_forever()
        except Exception as e:
            logging.error(f"Error in monitoring server: {e}")
            self.running = False

    def stop(self):
        """Stop the monitoring server."""
        if not self.running:
            return

        try:
            self.server.shutdown()
            self.server.server_close()
            self.running = False
            logging.info("Monitoring server stopped")
        except Exception as e:
            logging.error(f"Error stopping monitoring server: {e}")
