#!/usr/bin/env python3
"""
Data Generator for creating synthetic event data.
Supports multiple event types (transaction, security, web access, customer),
with options for batch generation and continuous streaming.

Features:
- Multiple event types with realistic data patterns
- Geographic distribution across regions
- Time-series data generation with business hours bias
- Streaming capability with configurable rates
- Support for JSON and CSV output formats
"""

import csv
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Iterator, Tuple, TextIO
from faker import Faker
from faker.providers import BaseProvider
import json
import random
import uuid
import click
import signal
import sys
from pathlib import Path
from contextlib import ExitStack
from functools import lru_cache


class LocationProvider(BaseProvider):
    """Custom Faker provider for generating geographically accurate coordinates"""
    def coordinates_within_bounds(self, lat_range: List[float], lng_range: List[float]) -> tuple:
        """Generate coordinates within specified latitude/longitude bounds"""
        lat = random.uniform(lat_range[0], lat_range[1])
        lng = random.uniform(lng_range[0], lng_range[1])
        return round(lat, 6), round(lng, 6)


class AddressGenerator:
    """Generates realistic addresses within specified regions"""
    def __init__(self, faker: Faker, region_config: Dict):
        self.fake = faker
        self.region = region_config

    def generate(self) -> Dict:
        """Generate a complete address with geographic coordinates"""
        lat, lng = self.fake.coordinates_within_bounds(
            self.region['lat_range'],
            self.region['lng_range']
        )

        return {
            'street': self.fake.street_address(),
            'city': self.fake.city(),
            'state': self.fake.state(),
            'country': self.region['country'],
            'postal_code': self.fake.postcode(),
            'latitude': lat,
            'longitude': lng,
            'timezone': self.region['timezone']
        }


class ProductCatalog:
    """Manages a catalog of products with consistent attributes"""
    def __init__(self, config: Dict):
        self.fake = Faker()
        self.products = self._generate_catalog(config)

    def _generate_catalog(self, config: Dict) -> List[Dict]:
        """Generate a fixed set of products to maintain consistency across events"""
        return [{
            'product_id': str(uuid.uuid4()),
            'name': f"{self.fake.color_name()} {self.fake.word()} {category.rstrip('s')}",
            'category': category,
            'base_price': round(random.uniform(10, 1000), 2),
            'brand': self.fake.company(),
            'material': self.fake.word(),
            'color': self.fake.color_name(),
            'weight': round(random.uniform(0.1, 50), 2),
            'in_stock': random.choice([True, False]),
            'stock_quantity': random.randint(0, 1000) if random.random() < 0.8 else 0
        } for _ in range(config['num_products'])
            for category in [random.choice(config['categories'])]]

    def random_product(self) -> Dict:
        """Get a random product from the catalog"""
        return random.choice(self.products)


class EventGenerator:
    """Base class for event generators with common functionality"""
    def __init__(self, region: Dict, config: Dict):
        self.region = region
        self.config = config
        self.fake = Faker()
        self.fake.add_provider(LocationProvider)

    def base_event(self, timestamp: Optional[datetime] = None) -> Dict:
        """Create base event structure with common fields"""
        return {
            'event_id': str(uuid.uuid4()),
            'timestamp': timestamp.isoformat() if timestamp else datetime.now().isoformat(),
            'region_name': self.region['name'],
            'region_country': self.region['country'],
            'region_timezone': self.region['timezone']
        }


class CustomerGenerator(EventGenerator):
    """Generates customer profiles with consistent data across events"""
    def __init__(self, region: Dict, config: Dict, faker: Faker, address_generator: AddressGenerator):
        super().__init__(region, config)
        self.fake = faker
        self.address_generator = address_generator

    @lru_cache(maxsize=1000)  # Cache up to 1000 customer profiles
    def _generate_customer(self, customer_id: str) -> Dict:
        """Generate a new customer profile with the given ID"""
        return {
            'customer_id': customer_id,
            'email': self.fake.email(),
            'phone': self.fake.phone_number(),
            'first_name': self.fake.first_name(),
            'last_name': self.fake.last_name(),
            'birth_date': self.fake.date_of_birth().isoformat(),
            'gender': random.choice(['male', 'female', 'prefer_not_to_say']),
            'education': random.choice(['high_school', 'bachelors', 'masters', 'phd', 'other']),
            'occupation': self.fake.job(),
            'income_range': random.choice(['0-25k', '25k-50k', '50k-75k', '75k-100k', '100k+']),
            'language': self.fake.language_code(),
            'nationality': self.fake.country(),
            'address': self.address_generator.generate(),
            'preferences': {
                'communication': random.choice(['email', 'sms', 'both']),
                'marketing_opt_in': random.choice([True, False]),
            },
            'account_type': random.choice(['basic', 'premium', 'vip']),
            'account_status': random.choice(['active', 'inactive', 'suspended']),
            'registration_date': self.fake.date_time_this_year().isoformat(),
            'last_login': self.fake.date_time_between(start_date='-30d').isoformat(),
            'ssn': self.fake.ssn(),
            'credit_card': {
                'number': self.fake.credit_card_number(card_type='visa16'),
                'expiration': self.fake.credit_card_expire(),
                'cvv': self.fake.credit_card_security_code()
            },
        }

    def generate(self, timestamp: Optional[datetime] = None) -> Dict:
        """Generate or retrieve a cached customer profile"""
        customer_id = str(uuid.uuid4())
        customer_data = self._generate_customer(customer_id)
        return {
            **self.base_event(timestamp),
            **customer_data
        }

    def get_customer(self, customer_id: str) -> Dict:
        """Retrieve an existing customer by ID"""
        return self._generate_customer(customer_id)


class TransactionGenerator(EventGenerator):
    """Generates realistic transaction events with customer and product data"""
    def __init__(self, region: Dict, config: Dict, customer_gen: CustomerGenerator, product_catalog: ProductCatalog):
        super().__init__(region, config)
        self.customer_gen = customer_gen
        self.product_catalog = product_catalog
        self.settings = config['event_settings']['transaction']

    def generate(self, timestamp: Optional[datetime] = None) -> Dict:
        """Generate a complete transaction event with computed values"""
        product = self.product_catalog.random_product()
        customer = self.customer_gen.generate(timestamp)
        quantity = random.randint(1, 5)

        # Calculate financial details
        subtotal = product['base_price'] * quantity
        tax_rate = round(random.uniform(0.05, 0.15), 2)
        tax = round(subtotal * tax_rate, 2)
        total = subtotal + tax

        return {
            **self.base_event(timestamp),
            'transaction_id': str(uuid.uuid4()),
            # Customer information
            'customer_id': customer['customer_id'],
            'customer_email': customer['email'],
            'customer_type': customer['account_type'],
            # Product information
            'product_id': product['product_id'],
            'product_name': product['name'],
            'product_category': product['category'],
            # Transaction details
            'quantity': quantity,
            'unit_price': product['base_price'],
            'subtotal': subtotal,
            'tax_rate': tax_rate,
            'tax_amount': tax,
            'total_amount': total,
            'payment_method': random.choice(self.settings['payment_methods']),
            'payment_status': random.choice(self.settings['statuses']),
            'currency': 'USD',
            # Shipping information (keeping address nested as it's a coherent unit)
            'shipping_address': customer['address'],
            'shipping_method': random.choice(['standard', 'express', 'overnight']),
            'estimated_delivery': (datetime.now() + timedelta(days=random.randint(1, 7))).isoformat()
        }


class SecurityGenerator(EventGenerator):
    """Generates security-related events with realistic patterns"""
    def __init__(self, region: Dict, config: Dict):
        super().__init__(region, config)
        self.settings = config['event_settings']['security']

    def generate(self, timestamp: Optional[datetime] = None) -> Dict:
        """Generate a security event with geographic and device information"""
        lat, lng = self.fake.coordinates_within_bounds(
            self.region['lat_range'],
            self.region['lng_range']
        )

        return {
            **self.base_event(timestamp),
            'security_id': str(uuid.uuid4()),
            'category': random.choice(self.settings['categories']),
            'severity': random.choice(self.settings['severities']),
            # Source information
            'source_ip': self.fake.ipv4(),
            'source_user_agent': self.fake.user_agent(),
            'source_city': self.fake.city(),
            'source_country': self.region['country'],
            'source_latitude': lat,
            'source_longitude': lng,
            'source_device_os': random.choice(['Windows', 'MacOS', 'Linux', 'iOS', 'Android']),
            'source_device_browser': random.choice(['Chrome', 'Firefox', 'Safari', 'Edge']),
            'source_device_type': random.choice(['desktop', 'mobile', 'tablet']),
            # Session and target information
            'session_id': str(uuid.uuid4()),
            'target_type': random.choice(['user', 'system', 'data', 'network']),
            'target_id': str(uuid.uuid4()),
            'target_name': self.fake.bs(),
            # Action details
            'action_type': random.choice(['create', 'read', 'update', 'delete']),
            'action_status': random.choice(['success', 'failure', 'blocked']),
            'error_code': random.choice([None, '401', '403', '404', '500']) if random.random() < 0.3 else None,
            'attempt_count': random.randint(1, 3) if random.random() < 0.2 else 1
        }


class WebAccessGenerator(EventGenerator):
    """Generates web access logs with realistic patterns and status codes"""
    def __init__(self, region: Dict, config: Dict):
        super().__init__(region, config)
        self.settings = config['event_settings']['web_access']
        self.http_versions = ['HTTP/1.0', 'HTTP/1.1', 'HTTP/2.0']

    def generate(self, timestamp: Optional[datetime] = None) -> Dict:
        """Generate a web access event with realistic HTTP patterns"""
        endpoint = random.choice(self.settings['endpoints'])
        status_codes = [int(k) for k in self.settings['status_weights'].keys()]
        weights = list(self.settings['status_weights'].values())
        session_id = str(uuid.uuid4())

        return {
            **self.base_event(timestamp),
            # Request details
            'http_method': 'GET' if endpoint.startswith('/api') else random.choice(['GET', 'POST']),
            'request': endpoint,
            'http_version': random.choice(self.http_versions),
            'remote_user': None if random.random() < 0.8 else self.fake.user_name(),
            'user_agent': self.fake.user_agent(),
            'accept_language': self.fake.locale(),
            'referer': random.choice([None, 'https://google.com', 'https://bing.com', None]),
            # Client information
            'client_ip': self.fake.ipv4(),
            'client_country': self.region['country'],
            'client_city': self.fake.city(),
            'is_mobile': random.random() < 0.4,
            'is_bot': random.random() < 0.05,
            # Response information
            'status_code': random.choices(status_codes, weights=weights)[0],
            'request_size': random.randint(100, 2000),  # Request body size (smaller than response)
            'response_size': random.randint(1000, 50000),  # Response body size (typically larger)
            'response_time': round(random.gauss(200, 20), 2),
            # Session and server details
            'session_id': session_id,
            'server_id': f"web-{random.randint(1, 5)}",
            'datacenter': self.region['name'],
            'cache_hit': random.random() < 0.7
        }


class DataGenerator:
    """Main generator class that coordinates all event generation"""
    def __init__(self, config_path: str = 'config.json', regions: Optional[List[str]] = None):
        self.config = self._load_config(config_path)
        self.regions = self._filter_regions(regions)
        self.product_catalog = ProductCatalog(self.config['products'])

        # Initialize generators for each region
        self.generators = {}
        for region in self.regions:
            faker = Faker()
            faker.add_provider(LocationProvider)

            address_gen = AddressGenerator(faker, region)
            customer_gen = CustomerGenerator(region, self.config, faker, address_gen)

            self.generators[region['name']] = {
                'transaction': TransactionGenerator(region, self.config, customer_gen, self.product_catalog),
                'security': SecurityGenerator(region, self.config),
                'web_access': WebAccessGenerator(region, self.config),
                'customer': customer_gen,
            }

    def _load_config(self, config_path: str) -> Dict:
        """Load and parse configuration file"""
        with open(config_path, 'r') as f:
            return json.load(f)

    def _filter_regions(self, regions: Optional[List[str]]) -> List[Dict]:
        """Filter regions based on user input"""
        if not regions:
            return self.config['regions']

        # Create a mapping of region prefixes to full region names
        region_map = {}
        for r in self.config['regions']:
            name = r['name']
            region_map[name] = name  # exact match
            prefix = name.split('-')[0]  # prefix match (e.g., 'us' for 'us-east')
            if prefix not in region_map:
                region_map[prefix] = []
            if isinstance(region_map[prefix], list):
                region_map[prefix].append(name)

        # Filter regions based on input
        filtered_regions = []
        invalid_regions = []
        for r in regions:
            if r in region_map:
                if isinstance(region_map[r], list):
                    # If it's a prefix match, add all matching regions
                    filtered_regions.extend(reg for reg in self.config['regions'] 
                                         if reg['name'] in region_map[r])
                else:
                    # Exact match
                    filtered_regions.extend(reg for reg in self.config['regions'] 
                                         if reg['name'] == r)
            else:
                invalid_regions.append(r)

        if invalid_regions:
            available_regions = sorted(list(region_map.keys()))
            error_msg = (
                f"Invalid region(s): {', '.join(invalid_regions)}\n"
                f"Available regions: {', '.join(available_regions)}\n"
                f"You can specify either full region names (e.g., 'us-east') "
                f"or region prefixes (e.g., 'us' for all US regions)"
            )
            raise click.BadParameter(error_msg)

        if not filtered_regions:
            raise click.BadParameter("No valid regions selected")

        return filtered_regions

    def generate_event(self, event_type: str, timestamp: Optional[datetime] = None) -> Dict:
        """Generate a single event of specified type"""
        region = random.choice(self.regions)
        generator = self.generators[region['name']][event_type]
        return generator.generate(timestamp)

    def generate_time_series(
            self,
            event_type: str,
            start_date: datetime,
            end_date: datetime,
            events_per_hour: int = 5
    ) -> Iterator[Dict]:
        """Generate time-series data with business hours pattern"""
        current = start_date
        time_config = self.config['time_patterns']

        while current < end_date:
            # Calculate timestamps in sorted order for this hour
            interval = 3600 / events_per_hour  # seconds between events
            for i in range(events_per_hour):
                # Add some random variation within the interval
                jitter = random.uniform(0, min(interval * 0.8, 59))  # Cap jitter at 59 seconds
                event_time = current + timedelta(seconds=i * interval + jitter)
                
                # Don't generate events past end_date
                if event_time >= end_date:
                    break
                    
                yield self.generate_event(event_type, event_time)

            current += timedelta(hours=1)


def setup_signal_handlers():
    """Setup graceful shutdown handlers for SIGINT and SIGTERM"""
    def signal_handler(signum, frame):
        print("\nReceived signal to stop...", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


@click.group()
def cli():
    """Bacalhau Data Generator CLI - generates synthetic event data"""
    pass


class EventWriter:
    """Handles writing events to files with optional rotation"""
    def __init__(self, output_dir: Path, evt_type: str, format: str, rotate_interval: Optional[str] = None):
        self.output_dir = output_dir
        self.evt_type = evt_type
        self.format = format
        self.rotate_interval = rotate_interval
        self.current_file = None
        self.current_key = None
        self.csv_writer = None
        self.last_timestamp = None

    def get_rotation_key(self, timestamp: datetime) -> str:
        """Get the key for file rotation based on timestamp"""
        if not self.rotate_interval:
            return ''
        
        if self.rotate_interval == 'minute':
            return timestamp.strftime('%Y-%m-%d_%H-%M')
        elif self.rotate_interval == 'hour':
            return timestamp.strftime('%Y-%m-%d_%H')
        elif self.rotate_interval == 'day':
            return timestamp.strftime('%Y-%m-%d')
        else:  # month
            return timestamp.strftime('%Y-%m')

    def get_filename(self, rotation_key: str) -> Path:
        """Get the output filename"""
        base = f"{self.evt_type}_events"
        if rotation_key:
            base = f"{base}_{rotation_key}"
        return self.output_dir / f"{base}.{self.format}"

    def write_event(self, event: Dict):
        """Write a single event, handling rotation if needed"""
        timestamp = datetime.fromisoformat(event['timestamp'])
        
        # Ensure timestamps are moving forward
        if self.last_timestamp and timestamp <= self.last_timestamp:
            print(f"Warning: Out of order timestamp detected: {timestamp} <= {self.last_timestamp}", file=sys.stderr)
            return
        
        rotation_key = self.get_rotation_key(timestamp)

        # Check if we need to rotate file
        if rotation_key != self.current_key:
            if self.current_file:
                self.close_file()
            
            filename = self.get_filename(rotation_key)
            print(f"Writing to {filename}")
            
            self.current_file = open(filename, 'w', encoding='utf-8')
            self.current_key = rotation_key
            
            # Initialize file for JSON array format only
            if self.format == 'json':
                self.current_file.write('[\n')
            elif self.format == 'csv':
                self.csv_writer = csv.DictWriter(
                    self.current_file,
                    fieldnames=list(_flatten_dict(event).keys()),
                    dialect='unix'
                )
                self.csv_writer.writeheader()

        # Write the event
        if self.format == 'json':
            if self.current_file.tell() > 2:  # More than just '[\n'
                self.current_file.write(',\n')
            json.dump(event, self.current_file)
        elif self.format == 'jsonl':
            json.dump(event, self.current_file)
            self.current_file.write('\n')
        else:  # csv
            self.csv_writer.writerow(_flatten_dict(event))
        
        self.last_timestamp = timestamp

    def close_file(self):
        """Close current file if open"""
        if self.current_file:
            if self.format == 'json':
                self.current_file.write('\n]')
            self.current_file.close()
            self.current_file = None
            self.csv_writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_file()


class EventTimeIterator:
    """Iterator that yields timestamps based on event rate and time control.
    
    This iterator generates timestamps either in real-time (with actual delays) 
    or in simulated time (advancing timestamps without real delays).
    
    Args:
        start_time: When to start generating timestamps from
        rate: Number of events per second to generate
        end_time: Optional end time to stop generation (None for infinite)
        real_time: If True, use actual delays; if False, simulate time progression
    """
    def __init__(self, start_time: datetime, rate: float, 
                 end_time: Optional[datetime] = None,
                 real_time: bool = False):
        self.current_time = start_time
        self.end_time = end_time
        self.rate = rate  # events per second
        self.real_time = real_time
        self.interval = timedelta(seconds=1/rate)
        self.last_real_time = time.time() if real_time else None

    def __iter__(self):
        return self

    def __next__(self) -> datetime:
        """Generate next timestamp, respecting rate limits.
        
        In real-time mode, sleeps to maintain the specified rate.
        In simulated mode, advances timestamps without actual delays.
        
        Returns:
            datetime: The timestamp for the next event
        
        Raises:
            StopIteration: When end_time is reached
        """
        if self.end_time and self.current_time >= self.end_time:
            raise StopIteration

        event_time = self.current_time

        if self.real_time:
            # Real-time mode: sleep to maintain rate
            now = time.time()
            if self.last_real_time:
                sleep_time = max(0, (self.last_real_time + 1/self.rate) - now)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self.last_real_time = time.time()
            self.current_time = datetime.now()
        else:
            # Simulated time mode: advance by interval
            self.current_time += self.interval
            # Add small sleep to prevent CPU hogging in simulated mode
            time.sleep(0.0001)  # 0.1ms sleep

        return event_time


@cli.command()
@click.option('--count', '-n', default=100, 
              help='Number of events to generate (per interval if --rotate-interval is specified)')
@click.option('--output', '-o', default='/data', help='Output directory')
@click.option('--type', '-t', default='all',
              type=click.Choice(['all', 'transaction', 'security', 'web_access', 'customer']))
@click.option('--format', '-f', default='jsonl', 
              type=click.Choice(['json', 'jsonl', 'csv']),
              help='Output format: json (pretty array), jsonl (one JSON per line), or csv')
@click.option('--region', '-r', multiple=True, help='Specific regions to generate data for')
@click.option('--days', '-d', default=None, type=int, help='Generate events for last N days')
@click.option('--start-date', type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]),
              help='Start date (format: YYYY-MM-DD or YYYY-MM-DDThh:mm:ss)')
@click.option('--end-date', type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]),
              help='End date (defaults to now if not specified)')
@click.option('--rotate-interval', type=click.Choice(['minute', 'hour', 'day', 'month']),
              help='Split output into multiple files by interval')
def generate(count: int, output: str, type: str, format: str,
             region: tuple, days: Optional[int], start_date: datetime, 
             end_date: datetime, rotate_interval: str):
    """Generate synthetic event data"""
    generator = DataGenerator(regions=list(region) if region else None)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine time range
    if not start_date:
        start_date = datetime.now() - timedelta(days=days if days else 1)
    if not end_date:
        end_date = datetime.now()

    # Calculate required rate to generate count events in the time range
    total_seconds = (end_date - start_date).total_seconds()
    if rotate_interval:
        # Rate per rotation interval
        interval_seconds = {
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'month': 2592000,  # 30 days
        }[rotate_interval]
        rate = count / interval_seconds
    else:
        # Overall rate for the entire time range
        rate = count / total_seconds

    # Generate events
    event_types = ['transaction', 'security', 'web_access', 'customer'] if type == 'all' else [type]
    for evt_type in event_types:
        with EventWriter(output_dir, evt_type, format, rotate_interval) as writer:
            for event_time in EventTimeIterator(start_date, rate, end_date, real_time=False):
                event = generator.generate_event(evt_type, event_time)
                writer.write_event(event)


def validate_positive_float(ctx, param, value):
    if value <= 0:
        raise click.BadParameter('Value must be greater than 0')
    return value

def validate_non_negative_int(ctx, param, value):
    if value < 0:
        raise click.BadParameter('Value must be non-negative')
    return value

@cli.command()
@click.option('--rate', '-r', default=1.0, callback=validate_positive_float,
              help='Events per second')
@click.option('--type', '-t', default='all',
              type=click.Choice(['all', 'transaction', 'security', 'web_access', 'customer']))
@click.option('--duration', '-d', default=0, callback=validate_non_negative_int,
              help='Duration in seconds (0 for infinite)')
@click.option('--output', '-o', default='/data', help='Output directory')
@click.option('--format', '-f', default='jsonl', 
              type=click.Choice(['json', 'jsonl', 'csv']),
              help='Output format: json (pretty array), jsonl (one JSON per line), or csv')
@click.option('--region', '-r', multiple=True, help='Specific regions to generate data for')
@click.option('--rotate-interval', type=click.Choice(['minute', 'hour', 'day', 'month']),
              help='Split output into multiple files by interval')
def stream(rate: float, type: str, duration: int, output: str, format: str, 
          region: tuple, rotate_interval: str):
    """Stream synthetic event data"""
    setup_signal_handlers()
    
    generator = DataGenerator(regions=list(region) if region else None)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=duration) if duration else None
    
    event_types = ['transaction', 'security', 'web_access', 'customer'] if type == 'all' else [type]
    with ExitStack() as stack:
        writers = {
            evt_type: stack.enter_context(EventWriter(output_dir, evt_type, format, rotate_interval))
            for evt_type in event_types
        }

        try:
            for evt_type in event_types:
                for event_time in EventTimeIterator(start_time, rate, end_time, real_time=True):
                    event = generator.generate_event(evt_type, event_time)
                    writers[evt_type].write_event(event)
        except KeyboardInterrupt:
            print("\nStopping event generation...", file=sys.stderr)


def _flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """
    Recursively flatten a nested dictionary by concatenating keys with separator.
    Example:
        Input: {'a': 1, 'b': {'c': 2}}
        Output: {'a': 1, 'b_c': 2}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


if __name__ == '__main__':
    cli()
