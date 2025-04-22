#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "geopy",
#   "meteostat",
#   "elevation",
#   "geonamescache",
#   "pandas",
#   "python-dotenv",
#   "requests",
#   "aiohttp",
#   "tqdm",
#   "pandas",
#   "requests",
# ]
# ///
import argparse
import asyncio
import json
import os
import re
import warnings

import aiohttp
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Suppress pandas deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

CITIES = [
    "New York",
    "London",
    "Tokyo",
    "Paris",
    "Berlin",
    "Sydney",
    "Toronto",
    "Mumbai",
    "Beijing",
    "São Paulo",
    "Moscow",
    "Dubai",
    "Singapore",
    "Los Angeles",
    "Chicago",
    "Shanghai",
    "Mexico City",
    "Hong Kong",
    "Bangkok",
    "Istanbul",
    "Johannesburg",
    "Seoul",
    "Madrid",
    "Rome",
    "Amsterdam",
    "Vancouver",
    "San Francisco",
    "Melbourne",
    "Cairo",
    "Riyadh",
    "Jakarta",
    "Lagos",
    "Buenos Aires",
    "Delhi",
    "Athens",
    "Lisbon",
    "Stockholm",
    "Copenhagen",
    "Oslo",
    "Helsinki",
    "Zurich",
    "Vienna",
    "Brussels",
    "Warsaw",
    "Prague",
    "Budapest",
    "Dublin",
    "Manila",
    "Karachi",
    "Tehran",
]


def clean_name(name):
    """Remove non-alphabetic characters and convert to uppercase."""
    return re.sub(r"[^a-zA-Z]", "", name).upper()


def generate_unique_abbreviation(city_name, country_name, abbreviations):
    """Generate a unique abbreviation for a city."""
    # Clean the names
    city_name = clean_name(city_name)
    country_name = clean_name(country_name)

    parts = city_name.split()
    abbreviation = ""

    if parts:
        abbreviation = parts[0][:4]
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation

    # Attempt 3: First 2 of first, first of second, first of third
    if len(parts) >= 3:
        abbreviation = parts[0][:2] + parts[1][:1] + parts[2][:1]
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation
    elif len(parts) == 2:
        abbreviation = parts[0][:2] + parts[1][:2]
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation

    # Attempt 4: First 3 of city + first 2 of country
    country_abbr = country_name[:2]
    if parts:
        abbreviation = parts[0][:3] + country_abbr
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation
        abbreviation = city_name[:3] + country_abbr
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation

    # Attempt 5: Add a counter
    counter = 1
    base_abbreviation = (
        (parts[0][:2] if parts else city_name[:2]) if len(city_name) > 1 else city_name
    )
    while True:
        abbreviation = f"{base_abbreviation}{counter:02d}"
        if abbreviation not in abbreviations:
            abbreviations[abbreviation] = city_name
            return abbreviation
        counter += 1


async def fetch_data(session, url, headers):
    """Generic async fetch function with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:  # Rate limit
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                else:
                    return None
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error fetching {url}: {e}")
                return None
            await asyncio.sleep(2**attempt)
    return None


async def get_city_info(session, city_name):
    """Get city information asynchronously."""
    api_key = os.getenv("API_NINJAS_API_KEY")
    if not api_key:
        print("Warning: API_NINJAS_API_KEY not found in .env file")
        return None

    # Handle special cases for city names
    city_mapping = {
        "New York City": "New York",
        "Sao Paulo": "São Paulo",
        "St. Paul": "Saint Paul",
    }
    api_city_name = city_mapping.get(city_name, city_name)

    url = f"https://api.api-ninjas.com/v1/city?name={api_city_name}"
    headers = {"X-Api-Key": api_key}

    data = await fetch_data(session, url, headers)
    if data and len(data) > 0:
        return data[0]
    return None


async def get_weather_data(session, city_name, lat, lon):
    """Get weather data asynchronously."""
    api_key = os.getenv("API_NINJAS_API_KEY")
    if not api_key:
        return None

    # Get current weather
    current_url = f"https://api.api-ninjas.com/v1/weather?lat={lat}&lon={lon}"
    forecast_url = f"https://api.api-ninjas.com/v1/weatherforecast?lat={lat}&lon={lon}"
    headers = {"X-Api-Key": api_key}

    current_weather, forecast = await asyncio.gather(
        fetch_data(session, current_url, headers),
        fetch_data(session, forecast_url, headers),
    )

    if not current_weather or not forecast:
        return None

    return {
        "current": {
            "temperature_celsius": current_weather.get("temp"),
            "feels_like_celsius": current_weather.get("feels_like"),
            "humidity_percent": current_weather.get("humidity"),
            "min_temperature_celsius": current_weather.get("min_temp"),
            "max_temperature_celsius": current_weather.get("max_temp"),
            "wind_speed_mps": current_weather.get("wind_speed"),
            "wind_direction_degrees": current_weather.get("wind_degrees"),
            "cloud_cover_percent": current_weather.get("cloud_pct"),
            "sunrise_timestamp": current_weather.get("sunrise"),
            "sunset_timestamp": current_weather.get("sunset"),
        },
        "forecast": forecast,
    }


async def get_air_quality(session, city_name, lat, lon):
    """Get air quality data asynchronously."""
    api_key = os.getenv("API_NINJAS_API_KEY")
    if not api_key:
        return None

    # Try with city name first
    city_url = f"https://api.api-ninjas.com/v1/airquality?city={city_name}"
    coord_url = f"https://api.api-ninjas.com/v1/airquality?lat={lat}&lon={lon}"
    headers = {"X-Api-Key": api_key}

    # Try city name first, then coordinates
    air_quality = await fetch_data(session, city_url, headers)
    if not air_quality:
        air_quality = await fetch_data(session, coord_url, headers)

    if not air_quality:
        return None

    return {
        "overall_aqi": air_quality.get("overall_aqi"),
        "pollutants": {
            "CO": air_quality.get("CO", {}),
            "NO2": air_quality.get("NO2", {}),
            "O3": air_quality.get("O3", {}),
            "SO2": air_quality.get("SO2", {}),
            "PM2_5": air_quality.get("PM2.5", {}),
            "PM10": air_quality.get("PM10", {}),
        },
    }


async def get_population_data(session, country_name):
    """Get population data asynchronously."""
    api_key = os.getenv("API_NINJAS_API_KEY")
    if not api_key:
        return None

    url = f"https://api.api-ninjas.com/v1/population?country={country_name}"
    headers = {"X-Api-Key": api_key}

    data = await fetch_data(session, url, headers)
    if not data:
        return None

    # Get the most recent historical data
    current_data = data.get("historical_population", [{}])[0]
    forecast_data = data.get("population_forecast", [{}])[0]

    return {
        "current": {
            "population": current_data.get("population"),
            "yearly_change_percentage": current_data.get("yearly_change_percentage"),
            "yearly_change": current_data.get("yearly_change"),
            "migrants": current_data.get("migrants"),
            "median_age": current_data.get("median_age"),
            "fertility_rate": current_data.get("fertility_rate"),
            "density": current_data.get("density"),
            "urban_population_pct": current_data.get("urban_population_pct"),
            "urban_population": current_data.get("urban_population"),
            "percentage_of_world_population": current_data.get(
                "percentage_of_world_population"
            ),
            "rank": current_data.get("rank"),
        },
        "forecast": {
            "year": forecast_data.get("year"),
            "population": forecast_data.get("population"),
            "yearly_change_percentage": forecast_data.get("yearly_change_percentage"),
        },
    }


async def process_city(session, city, pbar, abbreviations):
    """Process a single city and update progress bar."""
    try:
        pbar.set_description(f"Processing {city}")
        city_info = await get_city_info(session, city)
        if not city_info:
            pbar.write(f"Could not find city data for: {city}")
            return None

        latitude = city_info["latitude"]
        longitude = city_info["longitude"]
        country = city_info["country"]
        population = city_info["population"]
        is_capital = city_info["is_capital"]

        # Get all data concurrently
        weather_data, air_quality, population_data = await asyncio.gather(
            get_weather_data(session, city, latitude, longitude),
            get_air_quality(session, city, latitude, longitude),
            get_population_data(session, country),
        )

        city_data = {
            "full_name": city,
            "latitude": latitude,
            "longitude": longitude,
            "country": country,
            "abbreviation": generate_unique_abbreviation(city, country, abbreviations),
            "population": population,
            "is_capital": is_capital,
            "weather": weather_data if weather_data else None,
            "air_quality": air_quality if air_quality else None,
            "population_data": population_data if population_data else None,
        }

        pbar.update(1)
        return city_data

    except Exception as e:
        pbar.write(f"Error processing {city}: {e}")
        return None


async def get_city_data(cities):
    """Main async function to process all cities."""
    city_data_list = []
    abbreviations = {}

    print(f"Starting to process {len(cities)} cities...")
    async with aiohttp.ClientSession() as session:
        # Process cities in batches of 10
        for i in range(0, len(cities), 10):
            batch = cities[i : i + 10]
            print(f"\nProcessing batch {i // 10 + 1} of {(len(cities) + 9) // 10}...")
            with tqdm(total=len(batch), desc="Cities", position=0, leave=True) as pbar:
                tasks = [
                    process_city(session, city, pbar, abbreviations) for city in batch
                ]
                results = await asyncio.gather(*tasks)
                city_data_list.extend([r for r in results if r is not None])
                print(f"Completed batch {i // 10 + 1}")

    print(f"\nSuccessfully processed {len(city_data_list)} out of {len(cities)} cities")
    return json.dumps({"cities": city_data_list}, indent=4)


def display_city_table(cities_data):
    """Display city data in a formatted table."""
    if not cities_data or "cities" not in cities_data:
        print("No city data available")
        return

    print("\nCity Data Summary:")
    print("-" * 150)
    print(
        f"{'City':<20} {'Abbr':<6} {'Country':<15} {'City Pop':<12} {'Country Pop':<15} {'Pop Growth':<12} {'Density':<10} {'Urban %':<8} {'Temp (°C)':<10} {'Humidity':<10} {'AQI':<6}"
    )
    print("-" * 150)

    for city in cities_data["cities"]:
        if not city:  # Skip None entries
            continue

        # Weather data
        temp = (
            city.get("weather", {}).get("current", {}).get("temperature_celsius", "N/A")
        )
        humidity = (
            city.get("weather", {}).get("current", {}).get("humidity_percent", "N/A")
        )
        aqi = city.get("air_quality", {}).get("overall_aqi", "N/A")

        # Population data
        pop_data = (
            city.get("population_data", {}).get("current", {})
            if city.get("population_data")
            else {}
        )
        city_pop = f"{city['population']:,}" if city.get("population") else "N/A"
        country_pop = (
            f"{pop_data.get('population', 'N/A'):,}"
            if pop_data and pop_data.get("population")
            else "N/A"
        )
        pop_growth = (
            f"{pop_data.get('yearly_change_percentage', 'N/A')}%"
            if pop_data and pop_data.get("yearly_change_percentage")
            else "N/A"
        )
        density = (
            f"{pop_data.get('density', 'N/A')}/km²"
            if pop_data and pop_data.get("density")
            else "N/A"
        )
        urban_pct = (
            f"{pop_data.get('urban_population_pct', 'N/A')}%"
            if pop_data and pop_data.get("urban_population_pct")
            else "N/A"
        )

        print(
            f"{city['full_name']:<20} {city['abbreviation']:<6} {city['country']:<15} "
            f"{city_pop:<12} {country_pop:<15} {pop_growth:<12} {density:<10} {urban_pct:<8} "
            f"{str(temp):<10} {str(humidity):<10} {str(aqi):<6}"
        )


def main():
    parser = argparse.ArgumentParser(description="City data management tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--generate", action="store_true", help="Generate cities.json file"
    )
    group.add_argument(
        "--read", type=str, help="Read and display data from specified JSON file"
    )
    args = parser.parse_args()

    if args.generate:
        print("Generating city data...")
        city_json_data = asyncio.run(get_city_data(CITIES))

        with open("cities.json", "w") as f:
            f.write(city_json_data)
        print("\nGenerated cities.json file")

        # Display the data in table format
        display_city_table(json.loads(city_json_data))

    elif args.read:
        try:
            with open(args.read, "r") as f:
                city_data = json.load(f)
            display_city_table(city_data)
        except FileNotFoundError:
            print(f"Error: File {args.read} not found")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in file {args.read}")


if __name__ == "__main__":
    main()
