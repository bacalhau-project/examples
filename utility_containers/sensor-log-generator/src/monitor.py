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
        # CHANGED: Only log successful requests (status codes 200-299)
        # AND ignore common paths like / and /favicon.ico
        if args and len(args) >= 3:  # Check length for request_line, status_code, size
            try:
                request_line = str(args[0]) # e.g., "GET / HTTP/1.1"
                status_code = int(args[1])

                # Extract path from request_line (e.g., "/")
                parts = request_line.split()
                path = parts[1] if len(parts) >= 2 else ""

                # Only log if status is 2xx and path is not ignored
                if 200 <= status_code < 300 and path not in ("/", "/favicon.ico"):
                    logging.info(f"Monitor server: {format % args}")
            except (ValueError, IndexError):
                # If parsing fails, fall back to original logging for safety
                # (This case should be rare with the standard http.server format)
                logging.info(f"Monitor server: {format % args}")
        else:
             # Fall back to original logging if args format is unexpected
            logging.info(f"Monitor server: {format % args}")

    # ADDED: New method to suppress error logging
    def log_error(self, format, *args):
        """Override to suppress error logging."""
        # Completely suppress error logging
        pass

    # ADDED: New method to handle malformed requests silently
    def handle_one_request(self):
        """Handle a single HTTP request.

        Override to silently ignore malformed requests.
        """
        try:
            super().handle_one_request()
        except Exception:
            # Silently drop any exception during request parsing
            self.close_connection = True

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
            self.simulator.database.is_healthy()
            if hasattr(self.simulator, "database")
            else False
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
        if hasattr(self.simulator, "database") and hasattr(
            self.simulator.database, "get_performance_stats"
        ):
            db_metrics = self.simulator.database.get_performance_stats()

        # Get sync stats
        sync_stats = {}
        if hasattr(self.simulator, "database") and hasattr(
            self.simulator.database, "get_sync_stats"
        ):
            sync_stats = self.simulator.database.get_sync_stats()

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

    def _handle_sample(self):
        """Loads the last ten entries from the database and sends them as a JSON response."""
        data = self.simulator.database.get_last_ten_entries()
        self._send_json_response(200, data)

    def _handle_db_stats(self):
        """Handle database statistics request."""
        try:
            if not hasattr(self.simulator, "database"):
                return self._send_json_response(
                    400, {"error": "Database not initialized"}
                )

            stats = self.simulator.database.get_database_stats()

            # Format the response with human-readable values
            formatted_stats = {
                "total_readings": stats["total_readings"],
                "database_size": {
                    "bytes": stats["database_size_bytes"],
                    "human_readable": self._format_bytes(stats["database_size_bytes"]),
                },
                "last_write": stats["last_write_timestamp"],
                "indexes": {
                    name: {"bytes": size, "human_readable": self._format_bytes(size)}
                    for name, size in stats["index_sizes"].items()
                },
                "table_stats": stats["table_stats"],
                "performance": {
                    "total_inserts": stats["performance_metrics"]["total_inserts"],
                    "total_batches": stats["performance_metrics"]["total_batches"],
                    "avg_batch_size": round(
                        stats["performance_metrics"]["avg_batch_size"], 2
                    ),
                    "avg_insert_time_ms": round(
                        stats["performance_metrics"]["avg_insert_time_ms"], 2
                    ),
                    "total_insert_time_s": round(
                        stats["performance_metrics"]["total_insert_time_s"], 2
                    ),
                    "pending_batch_size": stats["performance_metrics"][
                        "pending_batch_size"
                    ],
                },
                "sync_status": {
                    "total": stats["sync_stats"]["total"],
                    "synced": stats["sync_stats"]["synced"],
                    "unsynced": stats["sync_stats"]["unsynced"],
                    "sync_percentage": round(stats["sync_stats"]["sync_percentage"], 2),
                },
                "anomalies": stats["anomaly_stats"],
            }

            # Include file paths and sizes in the response
            formatted_stats["files"] = stats.get("files", {})
            return self._send_json_response(200, formatted_stats)
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")
            return self._send_json_response(500, {"error": str(e)})

    def _format_bytes(self, size_bytes):
        """Format bytes into human-readable string."""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        while size_bytes >= 1024 and i < len(size_name) - 1:
            size_bytes /= 1024
            i += 1
        return f"{size_bytes:.2f} {size_name[i]}"

    def do_GET(self):
        """Handle GET requests."""
        # ADDED: Reject GET requests with a body
        content_length = self.headers.get('Content-Length')
        if content_length and int(content_length) > 0:
            self.send_error(400, "GET requests must not have a body")
            return
        # END ADDED

        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Route to appropriate handler based on path
        if path == "/healthz":
            self._handle_health()
        elif path == "/metricz":
            self._handle_metrics()
        elif path == "/statusz":
            self._handle_status()
        elif path == "/samplez":
            self._handle_sample()
        elif path == "/db_stats":
            self._handle_db_stats()
        else:
            # Default to showing available endpoints
            endpoints = {
                "endpoints": {
                    "/healthz": "Health check endpoint",
                    "/metricz": "JSON metrics endpoint",
                    "/statusz": "Simulator status endpoint",
                    "/samplez": "Sample data endpoint",
                    "/db_stats": "Database statistics endpoint",
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
