#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "databricks-sql-connector>=3.0.0",
#     "pyyaml>=6.0.2",
#     "pydantic>=2.0.0",
#     "fastapi>=0.100.0",
#     "uvicorn>=0.23.0",
#     "pandas>=2.2.3",
#     "jinja2>=3.0.0",
#     "moto>=4.0.0",
#     "pytest>=7.0.0"
# ]
# ///
"""
Autoloader Main Execution Script - The ONLY way to execute the sensor data pipeline.

This script replaces ALL previous execution methods and uses ONLY Autoloader + UC Volumes.
No direct Databricks SQL uploads, no alternative execution paths.

Usage:
  uv run -s autoloader_main.py setup                    # Setup infrastructure
  uv run -s autoloader_main.py process                  # Process data once
  uv run -s autoloader_main.py monitor                  # Start monitoring dashboard
  uv run -s autoloader_main.py continuous               # Continuous processing
  uv run -s autoloader_main.py test                     # Run all tests
  uv run -s autoloader_main.py status                   # Check system status
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from autoloader_monitoring_dashboard import AutoloaderMonitor
from autoloader_pipeline_manager import AutoloaderPipelineManager
from autoloader_tests import AutoloaderWorkflowTester
from s3_autoloader_landing_service import S3AutoloaderLandingService

# Import our Autoloader components (ONLY these - no old components)
from setup_unity_catalog_infrastructure import UnityCatalogInfrastructure


class AutoloaderMain:
    """Main execution class for Autoloader-only pipeline."""

    def __init__(self):
        """Initialize with default configurations."""
        self.uc_config = "unity_catalog_config.yaml"
        self.s3_config = "s3-uploader-config.yaml"
        self.db_path = "sensor_data.db"

        # Validate configuration files exist
        self._validate_configs()

    def _validate_configs(self):
        """Validate required configuration files exist."""
        required_files = [self.uc_config]
        missing_files = [f for f in required_files if not Path(f).exists()]

        if missing_files:
            print(f"❌ Missing required configuration files: {', '.join(missing_files)}")
            print("Run: uv run -s autoloader_main.py setup")
            sys.exit(1)

    def setup_infrastructure(self, args) -> int:
        """Setup complete Autoloader infrastructure."""
        print("🚀 Setting up Autoloader infrastructure...")

        try:
            # 1. Setup Unity Catalog infrastructure
            print("📋 Setting up Unity Catalog...")
            uc_infra = UnityCatalogInfrastructure(self.uc_config)
            if not uc_infra.setup_infrastructure():
                print("❌ Unity Catalog setup failed")
                return 1

            # 2. Setup Autoloader pipelines
            print("⚡ Setting up Autoloader pipelines...")
            pipeline_manager = AutoloaderPipelineManager(self.uc_config)
            if not pipeline_manager.setup_all_tables():
                print("❌ Autoloader pipeline setup failed")
                return 1

            # 3. Validate setup
            print("🔍 Validating setup...")
            if not pipeline_manager.validate_setup():
                print("❌ Setup validation failed")
                return 1

            print("✅ Autoloader infrastructure setup completed!")
            print("\nNext steps:")
            print(f"  uv run -s autoloader_main.py process --db-path {self.db_path}")
            print("  uv run -s autoloader_main.py monitor")

            return 0

        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return 1

    def process_data(self, args) -> int:
        """Process data using Autoloader (replaces ALL old processing methods)."""
        print("📊 Processing data with Autoloader...")

        try:
            # Initialize S3 landing service (ONLY way to process data)
            service = S3AutoloaderLandingService(self.s3_config, self.uc_config)

            if args.continuous:
                print(f"🔄 Starting continuous processing (every {args.interval}s)")
                service.run_continuous_processing(
                    db_path=args.db_path,
                    table_name=args.table,
                    batch_size=args.batch_size,
                    interval_seconds=args.interval,
                )
            else:
                print(f"📈 Processing single batch from {args.db_path}")
                results = service.process_sqlite_to_autoloader(
                    db_path=args.db_path,
                    table_name=args.table,
                    batch_size=args.batch_size,
                    job_id=args.job_id,
                )

                print("\n📊 Processing Results:")
                print(f"Pipeline: {results['pipeline_type']}")
                print(f"Records: {results['total_records_processed']}")
                print(f"Uploads: {len(results['uploads'])}")
                for bucket_type, s3_uri in results["uploads"].items():
                    print(f"  - {bucket_type}: {s3_uri}")

            return 0

        except Exception as e:
            print(f"❌ Processing failed: {e}")
            return 1

    def start_monitoring(self, args) -> int:
        """Start monitoring dashboard."""
        print("📊 Starting Autoloader monitoring dashboard...")

        try:
            # Import uvicorn here to avoid dependency in other commands
            import uvicorn
            from autoloader_monitoring_dashboard import app, create_dashboard_template

            # Set configuration environment variables
            os.environ["S3_CONFIG"] = self.s3_config
            os.environ["UC_CONFIG"] = self.uc_config

            # Create dashboard template
            create_dashboard_template()

            print(f"🚀 Dashboard starting at http://{args.host}:{args.port}")
            print(f"📋 API docs at http://{args.host}:{args.port}/docs")

            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
            return 0

        except Exception as e:
            print(f"❌ Failed to start monitoring: {e}")
            return 1

    def run_tests(self, args) -> int:
        """Run comprehensive Autoloader tests."""
        print("🧪 Running Autoloader tests...")

        try:
            tester = AutoloaderWorkflowTester()

            if args.test_type == "all":
                results = tester.run_all_tests()
                print("✅ All tests completed successfully!")
            else:
                tester.setup_test_environment()

                if args.test_type == "raw":
                    tester.test_raw_pipeline()
                elif args.test_type == "schematized":
                    tester.test_schematized_pipeline()
                elif args.test_type == "s3-access":
                    tester.test_s3_access_validation()
                elif args.test_type == "partitioning":
                    tester.test_data_partitioning()

                print(f"✅ {args.test_type} test completed successfully!")

            return 0

        except Exception as e:
            print(f"❌ Tests failed: {e}")
            return 1

    def show_status(self, args) -> int:
        """Show system status."""
        print("📊 Autoloader System Status")
        print("=" * 40)

        try:
            # Check Unity Catalog infrastructure
            print("\n🏗️  Unity Catalog Infrastructure:")
            try:
                pipeline_manager = AutoloaderPipelineManager(self.uc_config)
                status = pipeline_manager.get_pipeline_status()
            except Exception as e:
                print(f"  ❌ Connection failed: {e}")
                status = {"tables": [], "timestamp": "unavailable"}

            print(f"Timestamp: {status['timestamp']}")
            print(f"Tables: {len(status['tables'])}")

            for table in status["tables"]:
                status_icon = "✅" if table["exists"] else "❌"
                print(f"  {status_icon} {table['name']}: {table['record_count']} records")

            # Check S3 landing service
            print("\n📁 S3 Landing Service:")
            try:
                service = S3AutoloaderLandingService(self.s3_config, self.uc_config)
                s3_valid = service.validate_s3_access()
                s3_icon = "✅" if s3_valid else "❌"
                print(f"  {s3_icon} S3 Access: {'Valid' if s3_valid else 'Failed'}")
            except Exception as e:
                print(f"  ❌ S3 Service failed: {e}")

            # Check monitoring
            print("\n📊 Monitoring:")
            try:
                monitor = AutoloaderMonitor(self.s3_config, self.uc_config)
                health = asyncio.run(monitor.get_system_health())
            except Exception as e:
                print(f"  ❌ Monitoring failed: {e}")
                health = {"overall_status": "unknown", "components": {}, "alerts": []}

            health_icon = "✅" if health["overall_status"] == "healthy" else "⚠️"
            print(f"  {health_icon} Overall Status: {health['overall_status']}")

            if "components" in health:
                if "databricks" in health["components"]:
                    print(
                        f"  📡 Databricks: {health['components']['databricks'].get('status', 'unknown')}"
                    )
                if "s3" in health["components"]:
                    s3_comp = health["components"]["s3"]
                    print(
                        f"  🗄️  S3 Buckets: {s3_comp.get('accessible_buckets', 0)}/{s3_comp.get('total_buckets', 0)}"
                    )

            if health["alerts"]:
                print("\n⚠️  Alerts:")
                for alert in health["alerts"]:
                    print(f"  - {alert['level'].upper()}: {alert['message']}")

            return 0

        except Exception as e:
            print(f"❌ Status check failed: {e}")
            return 1


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Autoloader Main - The ONLY way to execute sensor data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  setup      Setup Unity Catalog infrastructure and Autoloader pipelines
  process    Process data using Autoloader (replaces ALL old methods)
  monitor    Start monitoring dashboard
  test       Run comprehensive tests
  status     Show system status

Examples:
  uv run -s autoloader_main.py setup
  uv run -s autoloader_main.py process --db-path sensor_data.db
  uv run -s autoloader_main.py process --continuous --interval 60
  uv run -s autoloader_main.py monitor --port 8000
  uv run -s autoloader_main.py test --type all
  uv run -s autoloader_main.py status
        """,
    )

    # Global options
    parser.add_argument(
        "--uc-config", default="unity_catalog_config.yaml", help="Unity Catalog configuration file"
    )
    parser.add_argument(
        "--s3-config", default="s3-uploader-config.yaml", help="S3 configuration file"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup infrastructure")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process data")
    process_parser.add_argument("--db-path", default="sensor_data.db", help="SQLite database path")
    process_parser.add_argument("--table", default="sensor_readings", help="Table name")
    process_parser.add_argument("--batch-size", type=int, default=1000, help="Batch size")
    process_parser.add_argument("--job-id", help="Job ID")
    process_parser.add_argument("--continuous", action="store_true", help="Continuous processing")
    process_parser.add_argument(
        "--interval", type=int, default=60, help="Interval for continuous mode (seconds)"
    )

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Start monitoring")
    monitor_parser.add_argument("--host", default="0.0.0.0", help="Host")
    monitor_parser.add_argument("--port", type=int, default=8000, help="Port")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument(
        "--type",
        dest="test_type",
        choices=["all", "raw", "schematized", "s3-access", "partitioning"],
        default="all",
        help="Test type",
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize main class
    main_exec = AutoloaderMain()
    main_exec.uc_config = args.uc_config
    main_exec.s3_config = args.s3_config

    # Execute command
    if args.command == "setup":
        return main_exec.setup_infrastructure(args)
    elif args.command == "process":
        return main_exec.process_data(args)
    elif args.command == "monitor":
        return main_exec.start_monitoring(args)
    elif args.command == "test":
        return main_exec.run_tests(args)
    elif args.command == "status":
        return main_exec.show_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
