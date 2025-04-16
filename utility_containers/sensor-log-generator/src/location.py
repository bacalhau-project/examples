import json
import logging
import os
import random
from typing import Dict, Tuple


class LocationGenerator:
    def __init__(self, config: Dict):
        """Initialize the location generator with configuration.

        Args:
            config: Configuration dictionary containing random_location settings
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.number_of_cities = config.get("number_of_cities", 10)
        self.gps_variation = config.get("gps_variation", 100)  # in meters
        self.cities_file = config.get("cities_file", "cities.json")

        # Get configured location information
        self.configured_city = config.get("city", "NOT_PROVIDED")
        self.configured_lat = config.get("latitude", "NOT_PROVIDED")
        self.configured_lon = config.get("longitude", "NOT_PROVIDED")

        # Set up logger
        self.logger = logging.getLogger(__name__)

        if self.enabled:
            self.cities = self._load_cities()
            self.logger.info(
                f"Random location generation enabled with {len(self.cities)} cities"
            )
        else:
            self.logger.info(
                f"Using configured location: {self.configured_city} at ({self.configured_lat}, {self.configured_lon})"
            )

    def _load_cities(self) -> Dict:
        """Load cities from file or generate random ones.

        Returns:
            Dictionary of cities with their GPS coordinates
        """
        try:
            # Get the absolute path to the cities file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cities_file_path = os.path.join(base_dir, self.cities_file)
            self.logger.info(f"Looking for cities file at: {cities_file_path}")

            # Try to load from file if it exists
            if os.path.exists(cities_file_path):
                self.logger.info(f"Found cities file at {cities_file_path}")
                with open(cities_file_path, "r") as f:
                    cities_data = json.load(f)
                    # The file has a top-level 'cities' key containing an array
                    cities_list = cities_data.get("cities", [])

                    # Sort cities by population in descending order
                    sorted_cities = sorted(
                        cities_list, key=lambda x: x.get("population", 0), reverse=True
                    )

                    # Take only the top N cities
                    top_cities = sorted_cities[: self.number_of_cities]

                    # Convert the list format to our expected dictionary format
                    cities = {}
                    for city in top_cities:
                        # Use the full_name as the key and store the coordinates
                        city_name = city.get("full_name", f"City_{len(cities) + 1}")
                        cities[city_name] = {
                            "latitude": city.get("latitude", 0),
                            "longitude": city.get("longitude", 0),
                            "country": city.get("country", "Unknown"),
                            "population": city.get("population", 0),
                        }

                    # Log the top cities by population
                    self.logger.info(
                        f"Top {self.number_of_cities} cities by population:"
                    )
                    for i, (name, data) in enumerate(cities.items(), 1):
                        self.logger.info(
                            f"{i}. {name}: Population {data['population']:,}"
                        )

                    return cities
            else:
                self.logger.warning(f"Cities file not found at {cities_file_path}")
        except Exception as e:
            self.logger.warning(f"Error loading cities file: {e}")

        # Generate random cities if file doesn't exist or loading failed
        cities = {}
        for i in range(self.number_of_cities):
            city_name = f"City_{i + 1}"
            # Generate random coordinates within reasonable bounds
            lat = random.uniform(-90, 90)
            lon = random.uniform(-180, 180)
            cities[city_name] = {
                "latitude": lat,
                "longitude": lon,
                "country": "Unknown",
                "population": 0,
            }
        self.logger.warning("Using randomly generated cities as fallback")
        return cities

    def _generate_random_offset(self) -> Tuple[float, float]:
        """Generate random GPS offset within specified variation.

        Returns:
            Tuple of (latitude_offset, longitude_offset) in degrees
        """
        # Convert meters to degrees (approximate)
        # 1 degree ≈ 111,320 meters at the equator
        variation_degrees = self.gps_variation / 111320.0

        # Generate random offsets
        lat_offset = random.uniform(-variation_degrees, variation_degrees)
        lon_offset = random.uniform(-variation_degrees, variation_degrees)

        self.logger.info(
            f"Generated random offsets: ({lat_offset:.6f}, {lon_offset:.6f})"
        )

        return lat_offset, lon_offset

    def generate_location(self) -> Tuple[str, float, float]:
        """Generate a random location.

        Returns:
            Tuple containing (city_name, latitude, longitude)
        """
        if not self.enabled:
            # Return configured values or None if not provided
            if (
                self.configured_lat != "NOT_PROVIDED"
                and self.configured_lon != "NOT_PROVIDED"
            ):
                return (
                    self.configured_city,
                    float(self.configured_lat),
                    float(self.configured_lon),
                )
            return None

        # Select a random city
        city_name = random.choice(list(self.cities.keys()))
        city_data = self.cities[city_name]
        base_lat = city_data["latitude"]
        base_lon = city_data["longitude"]

        # Add random variation to coordinates
        lat_offset, lon_offset = self._generate_random_offset()
        lat = base_lat + lat_offset
        lon = base_lon + lon_offset

        # Log the base location and the offset applied
        self.logger.info(
            f"Base city location: {city_name} at ({base_lat:.6f}, {base_lon:.6f})"
        )
        self.logger.info(f"Applied GPS offset: ({lat_offset:.6f}, {lon_offset:.6f})")
        self.logger.info(f"Final location: {city_name} at ({lat:.6f}, {lon:.6f})")

        return city_name, lat, lon

    def generate_replica_id(self, index: int, prefix: str = "SENSOR") -> str:
        """Generate a unique ID for a replica.

        Args:
            index: The replica index
            prefix: Prefix for the ID

        Returns:
            Formatted sensor ID
        """
        return f"{prefix}_{index}"
