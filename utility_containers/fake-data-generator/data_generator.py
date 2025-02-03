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
from typing import Dict, List, Optional, Iterator
from faker import Faker
from faker.providers import BaseProvider
import json
import random
import uuid
import click
import signal
import sys
from pathlib import Path


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
        self._cache = {}  # Cache customer profiles for consistency

    def generate(self, timestamp: Optional[datetime] = None) -> Dict:
        """Generate or retrieve a cached customer profile"""
        customer_id = str(uuid.uuid4())
        if customer_id not in self._cache:
            self._cache[customer_id] = {
                **self.base_event(timestamp),
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
        return self._cache[customer_id]


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
        if regions:
            return [r for r in self.config['regions'] if r['name'] in regions]
        return self.config['regions']

    def generate_event(self, event_type: str, timestamp: Optional[datetime] = None) -> Dict:
        """Generate a single event of specified type"""
        region = random.choice(self.regions)
        generator = self.generators[region['name']][event_type]
        return generator.generate(timestamp)

    def generate_batch(self, event_type: str, size: int) -> List[Dict]:
        """Generate a batch of events"""
        return [self.generate_event(event_type) for _ in range(size)]

    def generate_time_series(
            self,
            event_type: str,
            start_date: datetime,
            end_date: datetime,
            business_hours_bias: bool = True
    ) -> Iterator[Dict]:
        """Generate time-series data with business hours pattern"""
        current = start_date
        time_config = self.config['time_patterns']

        while current < end_date:
            # Determine number of events for this hour based on business hours
            if (business_hours_bias and
                    time_config['business_hours']['start'] <= current.hour <=
                    time_config['business_hours']['end']):
                num_events = random.randint(
                    time_config['business_hours']['event_range']['min'],
                    time_config['business_hours']['event_range']['max']
                )
            else:
                num_events = random.randint(
                    time_config['non_business_hours']['event_range']['min'],
                    time_config['non_business_hours']['event_range']['max']
                )

            # Generate events for this hour
            for _ in range(num_events):
                event_time = current + timedelta(minutes=random.randint(0, 59))
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


@cli.command()
@click.option('--count', '-n', default=100, help='Number of events to generate')
@click.option('--output', '-o', default='/data', help='Output directory')
@click.option('--type', '-t', default='all',
              type=click.Choice(['all', 'transaction', 'security', 'web_access', 'customer']))
@click.option('--format', '-f', default='json',
              type=click.Choice(['json', 'csv']))
@click.option('--region', '-r', multiple=True, help='Region(s) to generate data for')
@click.option('--time-series', is_flag=True, help='Generate time series data')
@click.option('--days', default=1, help='Number of days for time series data')
def generate(count: int, output: str, type: str, format: str,
             region: tuple, time_series: bool, days: int):
    """Generate a batch of synthetic event data with optional time series"""
    print(f"Starting data generation...")
    generator = DataGenerator(regions=list(region) if region else None)

    # Setup output directory
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine event types to generate
    event_types = ['transaction', 'security', 'web_access', 'customer'] if type == 'all' else [type]

    for evt_type in event_types:
        # Generate events based on mode (time-series or batch)
        if time_series:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            events = list(generator.generate_time_series(evt_type, start_date, end_date))
        else:
            events = generator.generate_batch(evt_type, count)

        output_path = output_dir / f"{evt_type}_events"

        # Write output in specified format
        if format == 'json':
            print(f"Writing {evt_type} events to {output_path}.json")
            with open(f"{output_path}.json", 'w') as f:
                json.dump(events, f, indent=2)
        else:  # csv
            if events:
                print(f"Writing {evt_type} events to {output_path}.csv")
                flat_event = _flatten_dict(events[0])
                fields = list(flat_event.keys())

                with open(f"{output_path}.csv", 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fields, dialect='unix')
                    writer.writeheader()
                    for event in events:
                        writer.writerow(_flatten_dict(event))


@cli.command()
@click.option('--rate', '-r', default=1.0, help='Events per second')
@click.option('--type', '-t', default='all',
              type=click.Choice(['all', 'transaction', 'security', 'web_access', 'customer']))
@click.option('--duration', '-d', default=0, help='Duration in seconds (0 for infinite)')
@click.option('--output', '-o', default='/data', help='Output directory')
@click.option('--format', '-f', default='json',
              type=click.Choice(['json', 'csv']))
@click.option('--region', '-r', multiple=True, help='Region(s) to generate data for')
def stream(rate: float, type: str, duration: int, output: str, format: str, region: tuple):
    """Generate continuous stream of synthetic event data with specified rate"""
    setup_signal_handlers()
    print(f"Starting event stream at {rate} events per second...", file=sys.stderr)

    # Initialize generator and output directory
    generator = DataGenerator(regions=list(region) if region else None)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup event generation parameters
    event_types = ['transaction', 'security', 'web_access', 'customer'] if type == 'all' else [type]
    start_time = datetime.now()
    interval = 1.0 / rate  # Time between events
    type_index = 0  # For round-robin event type selection

    try:
        # Setup output files
        output_files = {}
        for evt_type in event_types:
            output_path = output_dir / f"{evt_type}_stream.{format}"
            output_files[evt_type] = open(output_path, 'w', encoding='utf-8', buffering=1)  # Line buffering

        # Stream generation loop
        next_event_time = time.time() + interval
        while True:
            # Select event type (cycle through if 'all', otherwise just use the single type)
            evt_type = event_types[type_index] if len(event_types) > 1 else event_types[0]
            type_index = (type_index + 1) % len(event_types)

            # Generate and write event
            event = generator.generate_event(evt_type)

            if format == 'json':
                json.dump(event, output_files[evt_type])
                output_files[evt_type].write('\n')
            else:  # csv
                writer = csv.DictWriter(output_files[evt_type], fieldnames=list(_flatten_dict(event).keys()))
                writer.writerow(_flatten_dict(event))

            # Rate limiting
            now = time.time()
            if now < next_event_time:
                time.sleep(next_event_time - now)
            next_event_time += interval

            # Check duration
            if duration > 0 and (datetime.now() - start_time).total_seconds() >= duration:
                return

    except Exception as e:
        print(f"Error during stream generation: {e}", file=sys.stderr)
        raise

    finally:
        # Clean shutdown - close all output files
        for f in output_files.values():
            try:
                f.close()
            except Exception as e:
                print(f"Error closing file: {e}", file=sys.stderr)


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
