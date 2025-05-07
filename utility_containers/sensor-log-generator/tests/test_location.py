import json
import os
import random
import sys
import tempfile
import unittest

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from src.location import LocationGenerator


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


if __name__ == "__main__":
    unittest.main()
