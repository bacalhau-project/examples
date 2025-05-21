import json

# Suppress most logging output during tests
import logging
import math
import os
import random
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from main import process_identity_and_location  # Import from main.py
from src.location import LocationGenerator

# Add project root and src directory to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SRC_DIR)

logging.basicConfig(level=logging.CRITICAL)


class TestLocationGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Suppress logging messages from LocationGenerator during tests
        # by redirecting its logger to a NullHandler or setting level to CRITICAL
        # For simplicity here, we are not explicitly managing logger output in tests,
        # but in larger applications, you might want to.

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_temp_cities_file(self, cities_data):
        cities_file_path = os.path.join(self.temp_dir.name, "temp_cities.json")
        with open(cities_file_path, "w") as f:
            json.dump({"cities": cities_data}, f)
        return cities_file_path

    def test_generate_location_disabled_with_full_config(self):
        config = {
            "enabled": False,
            "city": "TestCity",
            "latitude": "12.345",
            "longitude": "67.890",
        }
        generator = LocationGenerator(config)
        city, lat, lon = generator.generate_location()
        self.assertEqual(city, "TestCity")
        self.assertEqual(lat, 12.345)
        self.assertEqual(lon, 67.890)

    def test_generate_location_disabled_missing_lat_long(self):
        scenarios = [
            {
                "enabled": False,
                "city": "TestCity",
                "latitude": "NOT_PROVIDED",
                "longitude": "67.890",
            },
            {
                "enabled": False,
                "city": "TestCity",
                "latitude": "12.345",
                "longitude": "NOT_PROVIDED",
            },
            {
                "enabled": False,
                "city": "TestCity",
                "latitude": "NOT_PROVIDED",
                "longitude": "NOT_PROVIDED",
            },
            {
                "enabled": False,
                "city": "NOT_PROVIDED",
                "latitude": "NOT_PROVIDED",
                "longitude": "NOT_PROVIDED",
            },
        ]
        for cfg in scenarios:
            with self.subTest(config=cfg):
                generator = LocationGenerator(cfg)
                result = generator.generate_location()
                self.assertIsNone(result, f"Expected None for config: {cfg}")

    def test_generate_location_enabled_with_cities_file(self):
        cities_data = [
            {
                "full_name": "CityA",
                "latitude": 10.0,
                "longitude": 20.0,
                "population": 1000,
            },
            {
                "full_name": "CityB",
                "latitude": 30.0,
                "longitude": 40.0,
                "population": 2000,
            },
        ]
        temp_cities_file = self._create_temp_cities_file(cities_data)

        config = {
            "enabled": True,
            "number_of_cities": 2,
            "gps_variation": 0,  # No variation for predictable testing of base coords
            "cities_file": os.path.basename(
                temp_cities_file
            ),  # Relative path to file in temp_dir
        }

        # LocationGenerator constructs path relative to its own file, so we need to adjust
        # For testing, we can mock os.path.dirname or ensure cities_file is findable
        # Easiest for this test: place the temp_cities.json where the code expects it (e.g., project root)
        # Or, modify LocationGenerator to accept an absolute path if a flag is set (test mode)
        # For now, we will assume cities_file can be an absolute path for easier testing.
        config["cities_file"] = (
            temp_cities_file  # Use absolute path for test simplicity
        )

        generator = LocationGenerator(config)
        self.assertEqual(len(generator.cities), 2)
        self.assertIn("CityA", generator.cities)
        self.assertIn("CityB", generator.cities)

        city, lat, lon = generator.generate_location()

        self.assertIn(city, ["CityA", "CityB"])
        if city == "CityA":
            self.assertEqual(lat, 10.0)
            self.assertEqual(lon, 20.0)
        else:  # CityB
            self.assertEqual(lat, 30.0)
            self.assertEqual(lon, 40.0)

    def test_generate_location_enabled_cities_file_takes_top_n_by_population(self):
        cities_data = [
            {
                "full_name": "CityPopLow",
                "latitude": 1.0,
                "longitude": 1.0,
                "population": 100,
            },
            {
                "full_name": "CityPopHigh",
                "latitude": 2.0,
                "longitude": 2.0,
                "population": 10000,
            },
            {
                "full_name": "CityPopMid",
                "latitude": 3.0,
                "longitude": 3.0,
                "population": 1000,
            },
        ]
        temp_cities_file = self._create_temp_cities_file(cities_data)

        config = {
            "enabled": True,
            "number_of_cities": 2,  # Should pick CityPopHigh and CityPopMid
            "gps_variation": 10,
            "cities_file": temp_cities_file,  # Absolute path
        }
        generator = LocationGenerator(config)
        self.assertEqual(len(generator.cities), 2)
        self.assertIn("CityPopHigh", generator.cities)
        self.assertIn("CityPopMid", generator.cities)
        self.assertNotIn("CityPopLow", generator.cities)

        # Test that one of the top N cities is generated
        for _ in range(
            5
        ):  # Generate a few times to increase chance of picking both if random
            city_name, _, _ = generator.generate_location()
            self.assertIn(city_name, ["CityPopHigh", "CityPopMid"])

    def test_generate_location_enabled_no_cities_file_generates_random(self):
        non_existent_file = os.path.join(self.temp_dir.name, "no_such_cities.json")
        config = {
            "enabled": True,
            "number_of_cities": 3,
            "gps_variation": 50,
            "cities_file": non_existent_file,
        }
        generator = LocationGenerator(config)
        self.assertEqual(len(generator.cities), 3)
        self.assertTrue(all(c.startswith("City_") for c in generator.cities.keys()))

        city, lat, lon = generator.generate_location()
        self.assertIn(city, generator.cities.keys())
        self.assertTrue(-90 <= lat <= 90)
        self.assertTrue(-180 <= lon <= 180)

        # Check that gps_variation is applied (lat/lon will not be exactly the base generated ones)
        # We can't know the exact base, but we can check it's not 0,0 unless randomly generated so
        base_lat = generator.cities[city]["latitude"]
        base_lon = generator.cities[city]["longitude"]
        if config["gps_variation"] > 0:
            self.assertTrue(
                lat != base_lat or lon != base_lon or (base_lat == 0 and base_lon == 0),
                "GPS variation should alter coordinates unless base is (0,0) and offset is also 0.",
            )
        else:
            self.assertEqual(lat, base_lat)
            self.assertEqual(lon, base_lon)


class TestProcessIdentityAndLocationInMain(unittest.TestCase):
    def setUp(self):
        self.base_identity = {
            "id": "test-sensor-001",  # Provide default ID to avoid triggering generation
            "location": "Testville",
            "latitude": 40.0,
            "longitude": -70.0,
            "timezone": "UTC",
            "manufacturer": "TestCorp",
            "model": "SensorX",
            "firmware_version": "1.0",
        }
        self.base_app_config = {
            "random_location": {
                "enabled": False,
                "gps_variation": 0,  # meters
                "cities_file": "dummy_cities.json",  # Will be mocked
            },
            "logging": {"level": "CRITICAL"},  # Suppress logs from tested function
            # Other config sections omitted for brevity
        }
        self.mock_city_data = {
            "GeneratedCity1": {"latitude": 10.0, "longitude": 20.0},
            "GeneratedCity2": {"latitude": 12.0, "longitude": 22.0},
        }
        self.temp_dir = tempfile.TemporaryDirectory()  # Added for helper

    def tearDown(self):  # Added for helper
        self.temp_dir.cleanup()

    def _create_temp_cities_file(self, cities_data_dict):
        """Helper to create a temporary cities.json file from a dictionary."""
        cities_list = [
            {
                "full_name": name,
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "population": 1000 + i * 100,  # Add varying population
            }
            for i, (name, data) in enumerate(cities_data_dict.items())
        ]
        cities_file_path = os.path.join(self.temp_dir.name, "temp_cities_for_main.json")
        with open(cities_file_path, "w") as f:
            json.dump({"cities": cities_list}, f)
        return cities_file_path

    @patch("main.generate_sensor_id", return_value="GENERATED_ID_MOCK")
    @patch("main.LocationGenerator")
    def test_location_specified_random_disabled_static_location(
        self, MockLocationGenerator, mock_generate_id
    ):
        """If location specified in identity and random_location is false, location should be static."""
        identity_data = self.base_identity.copy()
        app_config = self.base_app_config.copy()
        app_config["random_location"]["enabled"] = False
        app_config["random_location"]["gps_variation"] = 0  # Ensure no fuzzing

        processed_identity = process_identity_and_location(identity_data, app_config)

        self.assertEqual(processed_identity["location"], identity_data["location"])
        self.assertEqual(processed_identity["latitude"], identity_data["latitude"])
        self.assertEqual(processed_identity["longitude"], identity_data["longitude"])
        MockLocationGenerator.assert_not_called()  # LocationGenerator shouldn't be used

    @patch("main.generate_sensor_id", return_value="GENERATED_ID_MOCK")
    @patch(
        "main.LocationGenerator"
    )  # Mocked, but fuzzing uses math.random, not this directly for fuzz
    def test_location_specified_random_enabled_fuzzed_location(
        self, MockLocationGenerator, mock_generate_id
    ):
        """If location specified and random_location is true with variation, location should be fuzzed."""
        identity_data = self.base_identity.copy()
        initial_lat, initial_lon = identity_data["latitude"], identity_data["longitude"]

        app_config = self.base_app_config.copy()
        app_config["random_location"]["enabled"] = True
        app_config["random_location"]["gps_variation"] = 1000  # 1km variation

        processed_identity = process_identity_and_location(identity_data, app_config)

        self.assertEqual(
            processed_identity["location"], identity_data["location"]
        )  # Location name shouldn't change
        self.assertNotEqual(
            processed_identity["latitude"], initial_lat, "Latitude should be fuzzed"
        )
        self.assertNotEqual(
            processed_identity["longitude"], initial_lon, "Longitude should be fuzzed"
        )
        # Check if coordinates are reasonably close (e.g., within ~0.01 degrees for 1km fuzz)
        self.assertAlmostEqual(
            processed_identity["latitude"], initial_lat, delta=0.015
        )  # A bit more than 1km variation for lat
        self.assertAlmostEqual(
            processed_identity["longitude"],
            initial_lon,
            delta=0.015 / abs(math.cos(math.radians(initial_lat)))
            if abs(math.cos(math.radians(initial_lat))) > 0.01
            else 0.015,
        )

        MockLocationGenerator.assert_not_called()  # LocationGenerator not used if identity has full geo-info

    @patch("main.generate_sensor_id", return_value="GENERATED_ID_MOCK")
    def test_location_not_specified_random_enabled_generated_fuzzed_location(
        self, mock_generate_id
    ):
        """If no location specified and random_location true, a fuzzed location should be generated and not constant."""
        # Create a temporary cities file using self.mock_city_data
        temp_cities_file = self._create_temp_cities_file(self.mock_city_data)

        identity_data = self.base_identity.copy()
        del identity_data["location"]  # Remove location to trigger generation
        del identity_data["latitude"]
        del identity_data["longitude"]

        app_config = self.base_app_config.copy()
        app_config["random_location"]["enabled"] = True
        app_config["random_location"]["gps_variation"] = 1000  # 1km
        app_config["random_location"]["cities_file"] = temp_cities_file  # Use temp file
        app_config["random_location"]["number_of_cities"] = len(self.mock_city_data)

        # Run 1
        processed_identity1 = process_identity_and_location(
            identity_data.copy(), app_config
        )
        self.assertIn(processed_identity1["location"], self.mock_city_data.keys())
        base_city1_data = self.mock_city_data[processed_identity1["location"]]
        self.assertNotEqual(
            processed_identity1["latitude"], base_city1_data["latitude"]
        )
        self.assertNotEqual(
            processed_identity1["longitude"], base_city1_data["longitude"]
        )

        # Run 2 - to check if generated location is not constant (due to random.choice and fuzzing)
        # With a real LocationGenerator, city choice is random; fuzzing should ensure coord difference
        processed_identity2 = process_identity_and_location(
            identity_data.copy(), app_config
        )
        self.assertIn(processed_identity2["location"], self.mock_city_data.keys())
        base_city2_data = self.mock_city_data[processed_identity2["location"]]
        self.assertNotEqual(
            processed_identity2["latitude"], base_city2_data["latitude"]
        )
        self.assertNotEqual(
            processed_identity2["longitude"], base_city2_data["longitude"]
        )

        # Check that the two generated locations are different (either city name or fuzzed coords)
        # With fuzzing, even if the same city is picked, coords should differ.
        # If different cities are picked, location names will differ.
        location_different = (
            processed_identity1["location"] != processed_identity2["location"]
        )
        coords_different = (
            processed_identity1["latitude"] != processed_identity2["latitude"]
            or processed_identity1["longitude"] != processed_identity2["longitude"]
        )
        self.assertTrue(
            location_different or coords_different,
            "Generated locations/coords should not be constant across calls.",
        )

    @patch(
        "main.generate_sensor_id"
    )  # Not expected to be called if erroring before ID gen
    @patch("main.LocationGenerator")
    def test_location_not_specified_random_disabled_error(
        self, MockLocationGenerator, mock_generate_id
    ):
        """If no location specified and random_location is false, expect RuntimeError."""
        identity_data = self.base_identity.copy()
        del identity_data["location"]  # Remove location
        # Keep lat/lon or remove them too, either way it's an incomplete geo-spec without random enabled
        del identity_data["latitude"]
        del identity_data["longitude"]

        app_config = self.base_app_config.copy()
        app_config["random_location"]["enabled"] = False

        with self.assertRaisesRegex(
            RuntimeError, "Required geo-fields .* are missing or invalid"
        ):
            process_identity_and_location(identity_data, app_config)

        MockLocationGenerator.assert_not_called()
        mock_generate_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
