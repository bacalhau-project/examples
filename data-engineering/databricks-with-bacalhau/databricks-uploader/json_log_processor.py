#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0",
#     "pandas",
#     "pyarrow",
#     "click",
#     "pyyaml",
#     "python-dateutil",
# ]
# ///

"""
JSON Log Processor with Validation

This module converts flat sensor logs to structured JSON with comprehensive validation.
It supports multiple input formats and provides schema validation, data type checking,
and configurable output formatting.

Features:
- Flat log to JSON conversion
- Schema validation with Pydantic
- Support for nested JSON structures
- Configurable field mappings
- Data type coercion and validation
- Error handling and logging
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum

import click
import pandas as pd
import yaml
from pydantic import BaseModel, Field, validator, ValidationError
from dateutil import parser as date_parser


class SensorType(str, Enum):
    """Valid sensor types for wind turbines."""
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    RPM = "rpm"
    POWER = "power"
    WIND_SPEED = "wind_speed"
    PRESSURE = "pressure"
    HUMIDITY = "humidity"


class GPSCoordinate(BaseModel):
    """GPS coordinate with validation."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude: Optional[float] = Field(None, ge=-1000, le=10000)
    
    @validator('latitude', 'longitude')
    def validate_precision(cls, v):
        """Ensure reasonable GPS precision."""
        return round(v, 6)  # 6 decimal places = ~0.1m precision


class SensorReading(BaseModel):
    """Validated sensor reading model."""
    timestamp: datetime
    turbine_id: str = Field(..., regex=r'^WT-\d{4}$')
    sensor_type: SensorType
    value: float
    unit: str
    location: Optional[GPSCoordinate] = None
    quality_score: float = Field(..., ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Ensure timestamp is not in the future."""
        if v > datetime.now():
            raise ValueError("Timestamp cannot be in the future")
        return v
    
    @validator('value')
    def validate_value_range(cls, v, values):
        """Validate value is within reasonable range for sensor type."""
        sensor_type = values.get('sensor_type')
        if not sensor_type:
            return v
            
        ranges = {
            SensorType.TEMPERATURE: (-50, 150),  # Celsius
            SensorType.VIBRATION: (0, 100),      # mm/s
            SensorType.RPM: (0, 30),             # Wind turbine RPM
            SensorType.POWER: (0, 5000),         # kW
            SensorType.WIND_SPEED: (0, 50),      # m/s
            SensorType.PRESSURE: (900, 1100),    # hPa
            SensorType.HUMIDITY: (0, 100),       # %
        }
        
        min_val, max_val = ranges.get(sensor_type, (float('-inf'), float('inf')))
        if not min_val <= v <= max_val:
            raise ValueError(
                f"Value {v} out of range [{min_val}, {max_val}] for {sensor_type}"
            )
        return v


class LogProcessor:
    """Processes flat logs and converts them to validated JSON."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the processor with optional configuration."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path) if config_path else {}
        self.field_mappings = self.config.get('field_mappings', {})
        self.validation_rules = self.config.get('validation_rules', {})
        self.stats = {
            'processed': 0,
            'validated': 0,
            'errors': 0,
            'warnings': 0
        }
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def parse_flat_log(self, log_line: str) -> Dict[str, Any]:
        """Parse a flat log line into a dictionary."""
        # Common log formats
        patterns = [
            # ISO timestamp with key=value pairs
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(?P<data>.+)$',
            # Unix timestamp with JSON
            r'^(?P<timestamp>\d{10,13})\s+(?P<data>\{.+\})$',
            # CSV-like format
            r'^(?P<values>.+)$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, log_line.strip())
            if match:
                groups = match.groupdict()
                
                # Parse timestamp
                if 'timestamp' in groups:
                    timestamp = self._parse_timestamp(groups['timestamp'])
                else:
                    timestamp = datetime.now()
                
                # Parse data
                if 'data' in groups:
                    if groups['data'].startswith('{'):
                        # JSON data
                        data = json.loads(groups['data'])
                    else:
                        # Key=value pairs
                        data = self._parse_key_value_pairs(groups['data'])
                else:
                    # CSV format
                    data = self._parse_csv_line(groups.get('values', log_line))
                
                data['timestamp'] = timestamp
                return data
        
        # Fallback: treat entire line as message
        return {
            'timestamp': datetime.now(),
            'raw_message': log_line.strip()
        }
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse various timestamp formats."""
        # Unix timestamp
        if ts_str.isdigit():
            ts_int = int(ts_str)
            # Milliseconds
            if ts_int > 1e12:
                return datetime.fromtimestamp(ts_int / 1000)
            return datetime.fromtimestamp(ts_int)
        
        # ISO format or other
        return date_parser.parse(ts_str)
    
    def _parse_key_value_pairs(self, data_str: str) -> Dict[str, Any]:
        """Parse key=value pairs from a string."""
        result = {}
        # Handle quoted values
        pattern = r'(\w+)=(?:"([^"]+)"|([^\s]+))'
        
        for match in re.finditer(pattern, data_str):
            key = match.group(1)
            value = match.group(2) or match.group(3)
            
            # Try to convert to appropriate type
            result[key] = self._convert_value(value)
        
        return result
    
    def _parse_csv_line(self, line: str) -> Dict[str, Any]:
        """Parse CSV line using configured headers."""
        headers = self.config.get('csv_headers', [])
        values = line.split(',')
        
        if not headers:
            # Generate default headers
            headers = [f'field_{i}' for i in range(len(values))]
        
        return {
            headers[i]: self._convert_value(v.strip())
            for i, v in enumerate(values)
            if i < len(headers)
        }
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type."""
        # Boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Keep as string
        return value
    
    def apply_field_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply configured field mappings."""
        if not self.field_mappings:
            return data
        
        mapped = {}
        for old_key, new_key in self.field_mappings.items():
            if old_key in data:
                # Support nested keys with dot notation
                if '.' in new_key:
                    self._set_nested_value(mapped, new_key, data[old_key])
                else:
                    mapped[new_key] = data[old_key]
            elif old_key not in self.field_mappings.values():
                # Keep unmapped fields
                mapped[old_key] = data.get(old_key)
        
        # Add any unmapped fields
        for key, value in data.items():
            if key not in self.field_mappings and key not in mapped:
                mapped[key] = value
        
        return mapped
    
    def _set_nested_value(self, data: Dict, path: str, value: Any):
        """Set a value in a nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def validate_sensor_reading(self, data: Dict[str, Any]) -> Optional[SensorReading]:
        """Validate data against SensorReading model."""
        try:
            # Apply any data transformations
            if 'gps' in data and isinstance(data['gps'], str):
                # Parse GPS string "lat,lon,alt"
                parts = data['gps'].split(',')
                if len(parts) >= 2:
                    data['location'] = {
                        'latitude': float(parts[0]),
                        'longitude': float(parts[1]),
                        'altitude': float(parts[2]) if len(parts) > 2 else None
                    }
            
            reading = SensorReading(**data)
            self.stats['validated'] += 1
            return reading
            
        except ValidationError as e:
            self.logger.warning(f"Validation error: {e}")
            self.stats['errors'] += 1
            return None
    
    def process_log_file(self, 
                        input_path: str, 
                        output_path: str,
                        validate: bool = True,
                        batch_size: int = 1000) -> Dict[str, Any]:
        """Process an entire log file."""
        input_file = Path(input_path)
        output_file = Path(output_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        processed_records = []
        errors = []
        
        with open(input_file, 'r') as f:
            batch = []
            
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                
                try:
                    # Parse flat log
                    data = self.parse_flat_log(line)
                    
                    # Apply field mappings
                    data = self.apply_field_mappings(data)
                    
                    # Validate if requested
                    if validate:
                        reading = self.validate_sensor_reading(data)
                        if reading:
                            batch.append(reading.dict())
                        else:
                            errors.append({
                                'line': line_num,
                                'data': data,
                                'error': 'Validation failed'
                            })
                    else:
                        batch.append(data)
                    
                    self.stats['processed'] += 1
                    
                    # Write batch if full
                    if len(batch) >= batch_size:
                        self._write_batch(output_file, batch, append=len(processed_records) > 0)
                        processed_records.extend(batch)
                        batch = []
                        
                except Exception as e:
                    self.logger.error(f"Error processing line {line_num}: {e}")
                    errors.append({
                        'line': line_num,
                        'raw': line.strip(),
                        'error': str(e)
                    })
                    self.stats['errors'] += 1
            
            # Write final batch
            if batch:
                self._write_batch(output_file, batch, append=len(processed_records) > 0)
                processed_records.extend(batch)
        
        # Write error log if there are errors
        if errors:
            error_file = output_file.with_suffix('.errors.json')
            with open(error_file, 'w') as f:
                json.dump(errors, f, indent=2, default=str)
            self.logger.warning(f"Wrote {len(errors)} errors to {error_file}")
        
        return {
            'processed': self.stats['processed'],
            'validated': self.stats['validated'],
            'errors': self.stats['errors'],
            'output_file': str(output_file),
            'error_file': str(error_file) if errors else None
        }
    
    def _write_batch(self, output_file: Path, batch: List[Dict], append: bool = False):
        """Write a batch of records to JSON file."""
        mode = 'a' if append else 'w'
        
        # For JSON Lines format
        if output_file.suffix == '.jsonl':
            with open(output_file, mode) as f:
                for record in batch:
                    f.write(json.dumps(record, default=str) + '\n')
        else:
            # Standard JSON array
            if append and output_file.exists():
                # Read existing data
                with open(output_file, 'r') as f:
                    existing = json.load(f)
                existing.extend(batch)
                batch = existing
            
            with open(output_file, 'w') as f:
                json.dump(batch, f, indent=2, default=str)


@click.command()
@click.option('--input', '-i', required=True, help='Input log file path')
@click.option('--output', '-o', required=True, help='Output JSON file path')
@click.option('--config', '-c', help='Configuration file path')
@click.option('--validate/--no-validate', default=True, help='Enable validation')
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.option('--format', type=click.Choice(['json', 'jsonl']), default='json',
              help='Output format')
def main(input: str, output: str, config: str, validate: bool, 
         batch_size: int, format: str):
    """Convert flat sensor logs to validated JSON format."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Adjust output extension
    output_path = Path(output)
    if format == 'jsonl' and output_path.suffix != '.jsonl':
        output_path = output_path.with_suffix('.jsonl')
    
    # Process logs
    processor = LogProcessor(config)
    results = processor.process_log_file(
        input,
        str(output_path),
        validate=validate,
        batch_size=batch_size
    )
    
    # Print results
    click.echo(f"\nProcessing complete:")
    click.echo(f"  Processed: {results['processed']} lines")
    click.echo(f"  Validated: {results['validated']} records")
    click.echo(f"  Errors: {results['errors']}")
    click.echo(f"  Output: {results['output_file']}")
    
    if results.get('error_file'):
        click.echo(f"  Error log: {results['error_file']}")


if __name__ == '__main__':
    main()