#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pydantic>=2.0.0",
#   "boto3>=1.26.0",
#   "pyyaml>=6.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Main Pipeline Orchestrator

Coordinates all pipeline scenarios based on active configuration.
Designed to run continuously in a terminal window for local testing.
"""

import os
import sys
import time
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import signal
import threading

import yaml
import boto3
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

# Import pipeline components
from pipeline_manager_v2 import PipelineManagerV2, PipelineScenario
from lineage_enricher import LineageEnricher
from schematization_pipeline import SchematizationPipeline
from windowing_aggregator import WindowingAggregator
from anomaly_notifier import AnomalyNotifier
from simple_state_manager import SimpleStateManager


class PipelineOrchestrator:
    """Main orchestrator for all pipeline scenarios"""
    
    def __init__(self, config_path: str = "pipeline-config-v2.yaml"):
        self.console = Console()
        self.config_path = config_path
        self.config = self._load_config()
        
        # Initialize components
        self.pipeline_manager = PipelineManagerV2(
            self.config['pipeline'].get('state_db', 'pipeline_config.db')
        )
        self.lineage_enricher = LineageEnricher()
        
        # Component initialization flags
        self.components_initialized = False
        self.s3_client = None
        self.schematization = None
        self.aggregator = None
        self.notifier = None
        
        # State tracking
        self.running = False
        self.current_executions: Dict[PipelineScenario, Any] = {}
        self.stats = {
            'total_processed': 0,
            'by_scenario': {}
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Expand environment variables
        return self._expand_env_vars(config)
    
    def _expand_env_vars(self, config: Any) -> Any:
        """Recursively expand environment variables in config"""
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(v) for v in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            var_content = config[2:-1]  # Remove ${ and }
            
            # Handle ${VAR:-default} syntax
            if ':-' in var_content:
                var_name, default = var_content.split(':-', 1)
                return os.environ.get(var_name, default)
            # Handle ${VAR:default} syntax (without dash)
            elif ':' in var_content:
                var_name, default = var_content.split(':', 1)
                return os.environ.get(var_name, default)
            else:
                # No default value
                return os.environ.get(var_content, config)
        return config
    
    def _initialize_components(self, dry_run: bool = False):
        """Initialize pipeline components"""
        self.console.print("Initializing pipeline components...")
        
        # Debug: Print validation config
        self.console.print(f"[dim]Validation spec path: {self.config['validation']['spec_path']}[/dim]")
        
        # Initialize state manager
        state_dir = self.config['processing']['state_dir']
        os.makedirs(state_dir, exist_ok=True)
        self.state_manager = SimpleStateManager(state_dir)
        
        # Initialize windowing aggregator
        self.aggregator = WindowingAggregator(
            window_seconds=self.config['windowing']['interval_seconds'],
            aggregated_bucket=self.config['s3']['buckets']['aggregated'],
            dry_run=dry_run
        )
        
        # Initialize anomaly notifier
        self.notifier = AnomalyNotifier(
            config_path=self.config['validation']['spec_path'],
            sqs_queue_name=self.config['sqs']['queue_name'],
            dry_run=dry_run
        )
        
        self.components_initialized = True
        self.console.print("[green]✓ Components initialized[/green]")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.console.print("\n[yellow]Shutting down pipeline...[/yellow]")
        self.running = False
    
    def _read_sensor_data(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read sensor data from SQLite"""
        sqlite_path = self.config['sqlite']['path']
        table_name = self.config['sqlite']['table_name']
        
        # Check if database file exists
        if not os.path.exists(sqlite_path):
            self.console.print(f"\n[red]✗ Database file not found: {sqlite_path}[/red]")
            self.console.print("\n[yellow]To create test data, run:[/yellow]")
            self.console.print("[cyan]./create_test_sensor_data.py[/cyan]")
            raise FileNotFoundError(f"Database file not found: {sqlite_path}")
        
        try:
            conn = sqlite3.connect(sqlite_path)
            conn.row_factory = sqlite3.Row
            
            # Check if table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                self.console.print(f"\n[red]✗ Table '{table_name}' not found in database[/red]")
                self.console.print("\n[yellow]Available tables:[/yellow]")
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                for row in cursor:
                    self.console.print(f"  - {row[0]}")
                self.console.print("\n[yellow]To create test data, run:[/yellow]")
                self.console.print("[cyan]./create_test_sensor_data.py[/cyan]")
                raise ValueError(f"Table '{table_name}' not found in database")
            
            # Get last processed timestamp
            state = self.state_manager.load_state('orchestrator') or {}
            last_timestamp = state.get('last_timestamp', '2000-01-01T00:00:00')
            
            query = f"""
                SELECT * FROM {table_name}
                WHERE {self.config['sqlite']['timestamp_col']} > ?
                ORDER BY {self.config['sqlite']['timestamp_col']}
                LIMIT ?
            """
            
            cursor = conn.execute(query, (last_timestamp, limit))
            records = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return records
            
        except sqlite3.OperationalError as e:
            self.console.print(f"\n[red]✗ Database error: {str(e)}[/red]")
            self.console.print("\n[yellow]To create test data, run:[/yellow]")
            self.console.print("[cyan]./create_test_sensor_data.py[/cyan]")
            raise
    
    def _save_state(self, last_timestamp: str):
        """Save processing state"""
        state = {
            'last_timestamp': last_timestamp,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        self.state_manager.save_state('orchestrator', state)
    
    def _process_raw_scenario(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process RAW scenario - direct pass-through with lineage"""
        results = {
            'processed': 0,
            'uploaded': 0,
            'errors': []
        }
        
        for record in records:
            try:
                # Add lineage
                enriched = self.lineage_enricher.enrich_record(record)
                
                # Upload to raw bucket
                if self._upload_to_s3(
                    self.config['s3']['buckets']['raw'],
                    f"raw/{datetime.now().strftime('%Y/%m/%d')}/{record['sensor_id']}_{record['id']}.json",
                    enriched
                ):
                    results['uploaded'] += 1
                
                results['processed'] += 1
                
            except Exception as e:
                results['errors'].append(str(e))
        
        return results
    
    def _process_schematized_scenario(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process SCHEMATIZED scenario - validation with error routing"""
        # Process batch through schematization pipeline
        batch_results = self.schematization.process_batch(records)
        
        # Upload results
        upload_stats = self.schematization.upload_batch_results(batch_results)
        
        return {
            'processed': len(records),
            'valid': len(batch_results['schematized']),
            'invalid': len(batch_results['errors']),
            'uploaded_valid': upload_stats['schematized_uploaded'],
            'uploaded_errors': upload_stats['errors_uploaded']
        }
    
    def _process_lineage_scenario(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process LINEAGE scenario - enrich all records with lineage"""
        results = {
            'processed': 0,
            'uploaded': 0,
            'errors': []
        }
        
        # Enrich batch
        enriched_records = self.lineage_enricher.enrich_batch(records)
        
        # Upload to archival bucket
        for record in enriched_records:
            try:
                sensor_id = record['sensor_data'].get('sensor_id', 'unknown')
                if self._upload_to_s3(
                    self.config['s3']['buckets']['archival'],
                    f"lineage/{datetime.now().strftime('%Y/%m/%d')}/{sensor_id}_{datetime.now().timestamp()}.json",
                    record
                ):
                    results['uploaded'] += 1
                results['processed'] += 1
            except Exception as e:
                results['errors'].append(str(e))
        
        return results
    
    def _process_multi_destination_scenario(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process MULTI_DESTINATION scenario - archival + windowed aggregation"""
        results = {
            'processed': len(records),
            'archival_uploaded': 0,
            'windows_created': 0,
            'aggregated_uploaded': 0
        }
        
        # 1. Send to archival with lineage
        enriched_records = self.lineage_enricher.enrich_batch(records)
        for record in enriched_records:
            try:
                sensor_id = record['sensor_data'].get('sensor_id', 'unknown')
                if self._upload_to_s3(
                    self.config['s3']['buckets']['archival'],
                    f"multi/{datetime.now().strftime('%Y/%m/%d')}/{sensor_id}_{datetime.now().timestamp()}.json",
                    record
                ):
                    results['archival_uploaded'] += 1
            except Exception as e:
                pass
        
        # 2. Create windowed aggregations
        aggregated = self.aggregator.process_batch(records)
        results['windows_created'] = len(aggregated)
        results['aggregated_uploaded'] = self.aggregator.upload_aggregated_data(aggregated)
        
        return results
    
    def _process_notification_scenario(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process NOTIFICATION scenario - monitor for anomalies"""
        # Process through notifier
        return self.notifier.process_batch(records)
    
    def _upload_to_s3(self, bucket: str, key: str, data: Dict[str, Any]) -> bool:
        """Upload data to S3"""
        if not self.s3_client:
            return True  # Dry run
        
        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType='application/json'
            )
            return True
        except Exception as e:
            self.console.print(f"[red]S3 upload error: {e}[/red]")
            return False
    
    def _process_batch(self, records: List[Dict[str, Any]]) -> Dict[PipelineScenario, Dict[str, Any]]:
        """Process a batch of records through active scenarios"""
        active_scenarios = self.pipeline_manager.get_active_scenarios()
        results = {}
        
        for scenario in active_scenarios:
            try:
                # Start execution tracking
                if scenario not in self.current_executions:
                    exec_record = self.pipeline_manager.start_execution(scenario)
                    self.current_executions[scenario] = exec_record
                
                # Process based on scenario
                if scenario == PipelineScenario.RAW:
                    results[scenario] = self._process_raw_scenario(records)
                elif scenario == PipelineScenario.SCHEMATIZED:
                    results[scenario] = self._process_schematized_scenario(records)
                elif scenario == PipelineScenario.LINEAGE:
                    results[scenario] = self._process_lineage_scenario(records)
                elif scenario == PipelineScenario.MULTI_DESTINATION:
                    results[scenario] = self._process_multi_destination_scenario(records)
                elif scenario == PipelineScenario.NOTIFICATION:
                    results[scenario] = self._process_notification_scenario(records)
                
                # Update stats
                if scenario not in self.stats['by_scenario']:
                    self.stats['by_scenario'][scenario] = {
                        'total': 0,
                        'successful': 0,
                        'failed': 0
                    }
                
                scenario_stats = self.stats['by_scenario'][scenario]
                scenario_stats['total'] += results[scenario].get('processed', 0)
                
            except Exception as e:
                self.console.print(f"[red]Error in {scenario.value}: {e}[/red]")
                results[scenario] = {'error': str(e)}
        
        return results
    
    def _create_status_table(self) -> Table:
        """Create status table for display"""
        table = Table(title="Pipeline Status", show_header=True)
        table.add_column("Scenario", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Processed", justify="right")
        table.add_column("Success Rate", justify="right")
        table.add_column("Details")
        
        active_scenarios = self.pipeline_manager.get_active_scenarios()
        
        for scenario in PipelineScenario:
            if scenario in active_scenarios:
                stats = self.stats['by_scenario'].get(scenario, {})
                total = stats.get('total', 0)
                
                status = "🟢 Active" if scenario in self.current_executions else "⚪ Ready"
                success_rate = "100%" if total == 0 else f"{(stats.get('successful', 0) / total * 100):.1f}%"
                
                details = ""
                if scenario == PipelineScenario.SCHEMATIZED:
                    details = f"Valid: {stats.get('valid', 0)}, Invalid: {stats.get('invalid', 0)}"
                elif scenario == PipelineScenario.MULTI_DESTINATION:
                    details = f"Windows: {stats.get('windows', 0)}"
                elif scenario == PipelineScenario.NOTIFICATION:
                    details = f"Anomalies: {stats.get('anomalies', 0)}"
                
                table.add_row(
                    scenario.value,
                    status,
                    str(total),
                    success_rate,
                    details
                )
            else:
                table.add_row(
                    scenario.value,
                    "⚫ Inactive",
                    "-",
                    "-",
                    ""
                )
        
        return table
    
    def run(self, dry_run: bool = False, once: bool = False):
        """Run the pipeline orchestrator"""
        self.console.print(Panel.fit(
            "[bold cyan]Pipeline Orchestrator v2[/bold cyan]\n"
            f"Config: {self.config_path}\n"
            f"Mode: {'DRY RUN' if dry_run else 'LIVE'}"
        ))
        
        # Initialize components
        self._initialize_components(dry_run)
        
        # Get active scenarios
        active_scenarios = self.pipeline_manager.get_active_scenarios()
        self.console.print(f"Active scenarios: {[s.value for s in active_scenarios]}")
        
        self.running = True
        batch_count = 0
        
        with Live(self._create_status_table(), refresh_per_second=1) as live:
            while self.running:
                try:
                    # Read sensor data
                    records = self._read_sensor_data(
                        limit=self.config['processing']['batch_size']
                    )
                    
                    if records:
                        batch_count += 1
                        self.console.print(f"\n[cyan]Processing batch {batch_count} ({len(records)} records)...[/cyan]")
                        
                        # Process through active scenarios
                        results = self._process_batch(records)
                        
                        # Update state
                        last_timestamp = records[-1][self.config['sqlite']['timestamp_col']]
                        self._save_state(last_timestamp)
                        
                        # Update stats
                        self.stats['total_processed'] += len(records)
                        
                        # Update display
                        live.update(self._create_status_table())
                        
                        # Show results
                        for scenario, result in results.items():
                            if 'error' not in result:
                                self.console.print(f"  {scenario.value}: {result}")
                    else:
                        self.console.print("[dim]No new records to process[/dim]")
                    
                    if once:
                        break
                    
                    # Wait before next batch
                    time.sleep(self.config['processing']['upload_interval'])
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.console.print(f"[red]Pipeline error: {e}[/red]")
                    if once:
                        raise
        
        # Complete executions
        self._complete_executions()
        
        self.console.print("\n[green]Pipeline stopped[/green]")
        self.console.print(f"Total records processed: {self.stats['total_processed']}")
    
    def _complete_executions(self):
        """Complete all running executions"""
        for scenario, execution in self.current_executions.items():
            stats = self.stats['by_scenario'].get(scenario, {})
            
            try:
                self.pipeline_manager.complete_execution(
                    execution.id,
                    records_processed=stats.get('total', 0),
                    records_valid=stats.get('valid', 0),
                    records_invalid=stats.get('invalid', 0)
                )
            except Exception as e:
                self.console.print(f"[red]Failed to complete execution for {scenario.value}: {e}[/red]")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline Orchestrator")
    parser.add_argument("--config", default="pipeline-config-v2.yaml", help="Configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading to S3/SQS")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    
    args = parser.parse_args()
    
    orchestrator = PipelineOrchestrator(args.config)
    orchestrator.run(dry_run=args.dry_run, once=args.once)


if __name__ == "__main__":
    main()