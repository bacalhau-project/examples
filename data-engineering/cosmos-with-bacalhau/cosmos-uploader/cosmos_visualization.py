#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
#     "matplotlib",
#     "numpy",
# ]
# ///

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from cosmos_basic_operations import CosmosDBOperations
from cosmos_connection import CosmosDBConnection
from matplotlib.ticker import FuncFormatter

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CosmosDBMonitor:
    """
    Class for monitoring and visualizing Cosmos DB performance.
    """

    def __init__(self, operations: CosmosDBOperations, update_interval: float = 1.0):
        self.operations = operations
        self.update_interval = update_interval
        self.running = False
        self.monitor_thread = None

        # Data for visualization
        self.timestamps = []
        self.ru_per_second = []
        self.operations_per_second = []
        self.total_operations = []
        self.total_ru = []
        self.operation_counts = {
            "create": [],
            "upsert": [],
            "read": [],
            "query": [],
            "delete": [],
            "batch": [],
            "error": [],
        }

        # For calculating rates
        self.last_metrics = None
        self.start_time = time.time()

    def start_monitoring(self):
        """Start the monitoring thread."""
        if self.running:
            logger.warning("Monitoring is already running")
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Started Cosmos DB performance monitoring")

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            logger.info("Stopped Cosmos DB performance monitoring")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._collect_metrics()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(self.update_interval)

    def _collect_metrics(self):
        """Collect performance metrics."""
        current_metrics = self.operations.get_performance_metrics()
        current_time = time.time()

        # Calculate rates if we have previous metrics
        if self.last_metrics:
            time_diff = current_time - self.last_metrics["timestamp"]

            # RU per second in this interval
            ru_diff = (
                current_metrics["total_ru_consumed"]
                - self.last_metrics["total_ru_consumed"]
            )
            interval_ru_per_second = ru_diff / time_diff if time_diff > 0 else 0

            # Operations per second in this interval
            ops_diff = (
                current_metrics["total_operations"]
                - self.last_metrics["total_operations"]
            )
            interval_ops_per_second = ops_diff / time_diff if time_diff > 0 else 0

            # Store the data
            self.timestamps.append(current_time - self.start_time)
            self.ru_per_second.append(interval_ru_per_second)
            self.operations_per_second.append(interval_ops_per_second)
            self.total_operations.append(current_metrics["total_operations"])
            self.total_ru.append(current_metrics["total_ru_consumed"])

            # Store operation counts
            for op_type in self.operation_counts:
                current_count = current_metrics["operation_counts"].get(op_type, 0)
                self.operation_counts[op_type].append(current_count)

        # Store current metrics for next iteration
        self.last_metrics = {
            "timestamp": current_time,
            "total_ru_consumed": current_metrics["total_ru_consumed"],
            "total_operations": current_metrics["total_operations"],
            "operation_counts": current_metrics["operation_counts"].copy(),
        }

    def create_dashboard(self, fig_size: Tuple[int, int] = (12, 10)):
        """Create a dashboard for visualizing performance metrics."""
        fig = plt.figure(figsize=fig_size)
        fig.suptitle("Cosmos DB Performance Dashboard", fontsize=16)

        # Create subplots
        gs = fig.add_gridspec(3, 2)
        ax1 = fig.add_subplot(gs[0, 0])  # RU per second
        ax2 = fig.add_subplot(gs[0, 1])  # Operations per second
        ax3 = fig.add_subplot(gs[1, 0])  # Total RU consumed
        ax4 = fig.add_subplot(gs[1, 1])  # Total operations
        ax5 = fig.add_subplot(gs[2, :])  # Operation counts

        # Format y-axis to show thousands with 'k'
        def thousands_formatter(x, pos):
            return f"{x / 1000:.1f}k" if x >= 1000 else f"{x:.0f}"

        formatter = FuncFormatter(thousands_formatter)

        # Initialize empty plots
        (ru_line,) = ax1.plot([], [], "b-", label="RU/s")
        (ops_line,) = ax2.plot([], [], "g-", label="Ops/s")
        (total_ru_line,) = ax3.plot([], [], "b-", label="Total RU")
        (total_ops_line,) = ax4.plot([], [], "g-", label="Total Ops")

        # Operation counts lines
        op_lines = {}
        colors = ["r", "g", "b", "c", "m", "y", "k"]
        for i, op_type in enumerate(self.operation_counts):
            (op_lines[op_type],) = ax5.plot(
                [], [], f"{colors[i % len(colors)]}-", label=op_type
            )

        # Set labels and legends
        ax1.set_title("Request Units per Second")
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("RU/s")
        ax1.grid(True)
        ax1.legend()

        ax2.set_title("Operations per Second")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Ops/s")
        ax2.grid(True)
        ax2.legend()

        ax3.set_title("Total Request Units Consumed")
        ax3.set_xlabel("Time (s)")
        ax3.set_ylabel("RU")
        ax3.grid(True)
        ax3.legend()
        ax3.yaxis.set_major_formatter(formatter)

        ax4.set_title("Total Operations")
        ax4.set_xlabel("Time (s)")
        ax4.set_ylabel("Operations")
        ax4.grid(True)
        ax4.legend()
        ax4.yaxis.set_major_formatter(formatter)

        ax5.set_title("Operation Counts")
        ax5.set_xlabel("Time (s)")
        ax5.set_ylabel("Count")
        ax5.grid(True)
        ax5.legend()
        ax5.yaxis.set_major_formatter(formatter)

        # Function to update the plots
        def update_plot(frame):
            if not self.timestamps:
                return []

            # Update RU per second
            ru_line.set_data(self.timestamps, self.ru_per_second)
            ax1.relim()
            ax1.autoscale_view()

            # Update operations per second
            ops_line.set_data(self.timestamps, self.operations_per_second)
            ax2.relim()
            ax2.autoscale_view()

            # Update total RU
            total_ru_line.set_data(self.timestamps, self.total_ru)
            ax3.relim()
            ax3.autoscale_view()

            # Update total operations
            total_ops_line.set_data(self.timestamps, self.total_operations)
            ax4.relim()
            ax4.autoscale_view()

            # Update operation counts
            for op_type, line in op_lines.items():
                line.set_data(self.timestamps, self.operation_counts[op_type])
            ax5.relim()
            ax5.autoscale_view()

            return [ru_line, ops_line, total_ru_line, total_ops_line] + list(
                op_lines.values()
            )

        # Create animation
        ani = animation.FuncAnimation(
            fig, update_plot, interval=self.update_interval * 1000, blit=True
        )

        plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust for the title
        return fig, ani

    def show_dashboard(self):
        """Show the performance dashboard."""
        fig, ani = self.create_dashboard()
        plt.show()

    def save_metrics_to_file(self, filename: str):
        """Save collected metrics to a JSON file."""
        metrics_data = {
            "timestamps": self.timestamps,
            "ru_per_second": self.ru_per_second,
            "operations_per_second": self.operations_per_second,
            "total_operations": self.total_operations,
            "total_ru": self.total_ru,
            "operation_counts": self.operation_counts,
        }

        with open(filename, "w") as f:
            json.dump(metrics_data, f, indent=2)

        logger.info(f"Saved metrics to {filename}")

    def load_metrics_from_file(self, filename: str):
        """Load metrics from a JSON file."""
        with open(filename, "r") as f:
            metrics_data = json.load(f)

        self.timestamps = metrics_data["timestamps"]
        self.ru_per_second = metrics_data["ru_per_second"]
        self.operations_per_second = metrics_data["operations_per_second"]
        self.total_operations = metrics_data["total_operations"]
        self.total_ru = metrics_data["total_ru"]
        self.operation_counts = metrics_data["operation_counts"]

        logger.info(f"Loaded metrics from {filename}")


class DemoVisualization:
    """
    Class for creating the demo visualizations as described in the demo script.
    """

    def __init__(self, num_nodes: int = 5, regions: List[str] = None):
        self.num_nodes = num_nodes
        self.regions = regions or [
            "East US",
            "West US",
            "North Europe",
            "Southeast Asia",
            "Australia East",
        ]
        if len(self.regions) < self.num_nodes:
            self.regions = self.regions * (self.num_nodes // len(self.regions) + 1)
        self.regions = self.regions[: self.num_nodes]

        # Data for visualization
        self.node_throughput = np.zeros(self.num_nodes)
        self.global_ingestion_rate = 0
        self.network_bandwidth_saved = 0
        self.ru_consumption = []
        self.ru_timestamps = []

        # For animation
        self.running = False
        self.update_thread = None
        self.update_interval = 0.5  # seconds
        self.start_time = time.time()

    def start_demo(self):
        """Start the demo visualization."""
        if self.running:
            logger.warning("Demo is already running")
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info("Started demo visualization")

    def stop_demo(self):
        """Stop the demo visualization."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2.0)
            logger.info("Stopped demo visualization")

    def _update_loop(self):
        """Update the demo data."""
        while self.running:
            try:
                # Simulate data updates
                self._update_demo_data()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in demo update loop: {str(e)}")
                time.sleep(self.update_interval)

    def _update_demo_data(self):
        """Update the demo data with simulated values."""
        # Simulate node throughput (records/second)
        for i in range(self.num_nodes):
            # Ramp up throughput over time, with some randomness
            elapsed = time.time() - self.start_time
            max_throughput = 200000  # records per second per node
            ramp_factor = min(1.0, elapsed / 30.0)  # Ramp up over 30 seconds
            base_throughput = max_throughput * ramp_factor
            randomness = np.random.normal(0, 0.1)  # 10% randomness
            self.node_throughput[i] = max(0, base_throughput * (1 + randomness))

        # Update global ingestion rate
        self.global_ingestion_rate = np.sum(self.node_throughput)

        # Update network bandwidth saved (in GB)
        # Assume each record is about 1KB, and we save 85% by processing at the edge
        records_processed = self.global_ingestion_rate * self.update_interval
        data_size_gb = (
            records_processed * 1024 / (1024 * 1024 * 1024)
        )  # Convert KB to GB
        self.network_bandwidth_saved += data_size_gb * 0.85

        # Update RU consumption
        current_time = time.time() - self.start_time
        self.ru_timestamps.append(current_time)

        # Simulate RU consumption (about 5-10 RU per record, with some variation)
        ru_per_record = 5 + np.random.random() * 5
        current_ru = (
            self.global_ingestion_rate * ru_per_record / 1000
        )  # RU/s in thousands
        self.ru_consumption.append(current_ru)

        # Keep only the last 60 seconds of data for the RU graph
        if len(self.ru_timestamps) > 120:  # Assuming 0.5s update interval
            self.ru_timestamps = self.ru_timestamps[-120:]
            self.ru_consumption = self.ru_consumption[-120:]

    def create_dashboard(self, fig_size: Tuple[int, int] = (15, 10)):
        """Create the demo dashboard."""
        fig = plt.figure(figsize=fig_size)
        fig.suptitle("Azure Cosmos DB with Expanso - Live Demo", fontsize=16)

        # Create subplots
        gs = fig.add_gridspec(2, 2)
        ax1 = fig.add_subplot(gs[0, 0])  # Node throughput
        ax2 = fig.add_subplot(gs[0, 1])  # Global ingestion rate
        ax3 = fig.add_subplot(gs[1, 0])  # Network bandwidth saved
        ax4 = fig.add_subplot(gs[1, 1])  # RU consumption

        # Format y-axis to show thousands with 'k' and millions with 'M'
        def thousands_formatter(x, pos):
            if x >= 1000000:
                return f"{x / 1000000:.1f}M"
            elif x >= 1000:
                return f"{x / 1000:.1f}k"
            else:
                return f"{x:.0f}"

        formatter = FuncFormatter(thousands_formatter)

        # Node throughput bar chart
        bars = ax1.bar(range(self.num_nodes), self.node_throughput, color="skyblue")
        ax1.set_title("Per-Node Throughput")
        ax1.set_xlabel("Node")
        ax1.set_ylabel("Records/second")
        ax1.set_xticks(range(self.num_nodes))
        ax1.set_xticklabels(
            [f"Node {i + 1}\n{region}" for i, region in enumerate(self.regions)],
            rotation=45,
            ha="right",
        )
        ax1.yaxis.set_major_formatter(formatter)

        # Global ingestion rate gauge
        gauge_ax = ax2.add_patch(plt.Circle((0.5, 0.5), 0.4, color="lightgray"))
        ax2.text(0.5, 0.5, "0", ha="center", va="center", fontsize=24)
        ax2.text(0.5, 0.3, "Records/second", ha="center", va="center", fontsize=12)
        ax2.set_title("Global Ingestion Rate")
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.axis("off")

        # Network bandwidth saved gauge
        bandwidth_ax = ax3.add_patch(
            plt.Rectangle((0.1, 0.4), 0.8, 0.2, color="lightgray")
        )
        ax3.text(0.5, 0.5, "0 GB", ha="center", va="center", fontsize=18)
        ax3.text(
            0.5, 0.3, "Network Bandwidth Saved", ha="center", va="center", fontsize=12
        )
        ax3.set_title("Network Bandwidth Savings")
        ax3.set_xlim(0, 1)
        ax3.set_ylim(0, 1)
        ax3.axis("off")

        # RU consumption graph
        (ru_line,) = ax4.plot([], [], "r-", label="RU/s (thousands)")
        ax4.set_title("Cosmos DB RU Consumption")
        ax4.set_xlabel("Time (s)")
        ax4.set_ylabel("RU/s (thousands)")
        ax4.grid(True)
        ax4.legend()

        # Function to update the plots
        def update_plot(frame):
            # Update node throughput bars
            for i, bar in enumerate(bars):
                bar.set_height(self.node_throughput[i])
            ax1.set_ylim(0, max(self.node_throughput) * 1.1 or 1)

            # Update global ingestion rate gauge
            rate_text = ax2.texts[0]
            if self.global_ingestion_rate >= 1000000:
                rate_text.set_text(f"{self.global_ingestion_rate / 1000000:.2f}M")
            elif self.global_ingestion_rate >= 1000:
                rate_text.set_text(f"{self.global_ingestion_rate / 1000:.1f}k")
            else:
                rate_text.set_text(f"{self.global_ingestion_rate:.0f}")

            # Update color based on percentage of target (1M records/s)
            target_rate = 1000000
            percentage = min(1.0, self.global_ingestion_rate / target_rate)
            gauge_ax.set_color(plt.cm.RdYlGn(percentage))

            # Update network bandwidth saved
            bandwidth_text = ax3.texts[0]
            if self.network_bandwidth_saved >= 1000:
                bandwidth_text.set_text(f"{self.network_bandwidth_saved / 1000:.2f} TB")
            else:
                bandwidth_text.set_text(f"{self.network_bandwidth_saved:.2f} GB")

            # Update bandwidth gauge fill
            bandwidth_ax.set_width(
                min(0.8, self.network_bandwidth_saved / 3000 * 0.8)
            )  # Max at 3TB

            # Update RU consumption graph
            if self.ru_timestamps:
                ru_line.set_data(self.ru_timestamps, self.ru_consumption)
                ax4.set_xlim(
                    max(0, self.ru_timestamps[-1] - 60), self.ru_timestamps[-1] + 1
                )
                ax4.set_ylim(0, max(self.ru_consumption) * 1.1 or 1)

            return bars + [gauge_ax, bandwidth_ax, ru_line] + ax2.texts + ax3.texts

        # Create animation
        ani = animation.FuncAnimation(
            fig, update_plot, interval=self.update_interval * 1000, blit=True
        )

        plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust for the title
        return fig, ani

    def show_dashboard(self):
        """Show the demo dashboard."""
        fig, ani = self.create_dashboard()
        plt.show()


def main(config_path: str = None):
    """Run the visualization demo."""
    try:
        if config_path:
            # Initialize with real Cosmos DB connection
            cosmos_connection = CosmosDBConnection(config_path)
            operations = CosmosDBOperations(cosmos_connection)

            # Create and start the monitor
            monitor = CosmosDBMonitor(operations)
            monitor.start_monitoring()

            # Show the dashboard
            monitor.show_dashboard()

            # Clean up
            monitor.stop_monitoring()
        else:
            # Run the demo visualization without Cosmos DB connection
            demo = DemoVisualization()
            demo.start_demo()
            demo.show_dashboard()
            demo.stop_demo()

        return True
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        success = main(sys.argv[1])
    else:
        success = main()

    sys.exit(0 if success else 1)
