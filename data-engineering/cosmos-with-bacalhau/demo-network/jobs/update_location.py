#!/usr/bin/env python3
import json
import os
import random
import sys
import secrets
import math

# Enable debug output if DEBUG environment variable is set
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, file=sys.stderr, **kwargs)

# Region definitions
EMEA_COUNTRIES = ["GB", "DE", "FR", "IT", "ES", "NL", "SE", "CH", "AE", "SA", "ZA", "EG", "TR", "IL"]
NA_COUNTRIES = ["US", "CA", "MX"]
LATAM_COUNTRIES = ["BR", "AR", "CO", "CL", "PE", "VE", "EC", "UY", "PY", "BO"]
APAC_COUNTRIES = ["CN", "JP", "KR", "IN", "AU", "SG", "MY", "TH", "VN", "ID", "PH", "NZ"]

# Region weightings (must sum to 1.0)
REGION_WEIGHTS = {
    "EMEA": 0.35,  # 35%
    "NA": 0.25,    # 25%
    "LATAM": 0.15, # 15%
    "APAC": 0.25   # 25%
}

def get_region_for_country(country_code):
    """Return the region for a given country code."""
    if country_code in EMEA_COUNTRIES:
        return "EMEA"
    elif country_code in NA_COUNTRIES:
        return "NA"
    elif country_code in LATAM_COUNTRIES:
        return "LATAM"
    elif country_code in APAC_COUNTRIES:
        return "APAC"
    return None

def generate_fuzzy_coordinates(lat, lon, max_distance_km=3):
    """
    Generate random coordinates within max_distance_km of the original point.
    Uses the Haversine formula to ensure the new point is within the specified distance.
    """
    # Earth's radius in kilometers
    R = 6371
    
    # Convert max distance to radians
    max_distance_rad = max_distance_km / R
    
    # Convert original coordinates to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    # Generate random distance and bearing
    distance = random.uniform(0, max_distance_rad)
    bearing = random.uniform(0, 2 * math.pi)
    
    # Calculate new coordinates
    new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance) +
                           math.cos(lat_rad) * math.sin(distance) * math.cos(bearing))
    
    new_lon_rad = lon_rad + math.atan2(math.sin(bearing) * math.sin(distance) * math.cos(lat_rad),
                                      math.cos(distance) - math.sin(lat_rad) * math.sin(new_lat_rad))
    
    # Convert back to degrees
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)
    
    return new_lat, new_lon

def select_city_by_region(cities):
    """Select a city based on regional weightings."""
    # Group cities by region
    cities_by_region = {
        "EMEA": [],
        "NA": [],
        "LATAM": [],
        "APAC": []
    }
    
    for city in cities:
        region = get_region_for_country(city['country'])
        if region:
            cities_by_region[region].append(city)
    
    # Print debug info
    debug_print("\n=== City Selection Debug ===")
    debug_print("Cities by region:")
    for region, city_list in cities_by_region.items():
        debug_print(f"{region}: {len(city_list)} cities")
        if city_list:
            debug_print(f"  Example: {city_list[0]['full_name']}, {city_list[0]['country']}")
    
    # Select region based on weights
    region = random.choices(
        list(REGION_WEIGHTS.keys()),
        weights=list(REGION_WEIGHTS.values()),
        k=1
    )[0]
    
    debug_print(f"\nSelected region: {region}")
    debug_print(f"Region weights: {REGION_WEIGHTS}")
    
    # Select random city from chosen region
    if cities_by_region[region]:
        selected = random.choice(cities_by_region[region])
        debug_print(f"Selected city: {selected['full_name']}, {selected['country']}")
        return selected
    
    # Fallback to random selection if region is empty
    debug_print("Region empty, falling back to random selection")
    selected = random.choice(cities)
    debug_print(f"Selected city: {selected['full_name']}, {selected['country']}")
    return selected

def main():
    try:
        debug_print("\n=== Container Startup Debug ===")
        debug_print(f"Container ID: {os.getenv('HOSTNAME', 'unknown')}")
        debug_print(f"Process ID: {os.getpid()}")
        
        # Seed random number generator with system entropy
        seed = secrets.randbits(128)
        random.seed(seed)
        debug_print(f"Random seed: {seed}")
        
        # Read node identity file
        with open('/root/node_identity.json', 'r') as f:
            node_identity = json.load(f)
        debug_print(f"\nOriginal node identity: {json.dumps(node_identity, indent=2)}")
        
        # Read cities file
        with open('/root/cities.json', 'r') as f:
            cities = json.load(f)
        
        debug_print(f"\nTotal cities loaded: {len(cities)}")
        debug_print("First 5 cities:")
        for city in cities[:5]:
            debug_print(f"  {city['full_name']}, {city['country']}")
            debug_print(f"  Coordinates: {city.get('latitude', 'N/A')}, {city.get('longitude', 'N/A')}")
        
        # Select a city based on regional weightings
        selected_city = select_city_by_region(cities)
        
        # Get coordinates from the selected city
        if 'latitude' not in selected_city or 'longitude' not in selected_city:
            debug_print(f"Error: Selected city {selected_city['full_name']} missing coordinates")
            debug_print(f"City data: {json.dumps(selected_city, indent=2)}")
            sys.exit(1)
        
        # Generate fuzzy coordinates within 3km of the city
        original_lat = selected_city['latitude']
        original_lon = selected_city['longitude']
        fuzzy_lat, fuzzy_lon = generate_fuzzy_coordinates(original_lat, original_lon)
        
        # Update location and coordinates
        node_identity['location'] = selected_city['full_name']
        node_identity['latitude'] = fuzzy_lat
        node_identity['longitude'] = fuzzy_lon
        
        # Write to mounted directory
        with open('/root/node_identity.json', 'w') as f:
            json.dump(node_identity, f, indent=4)
        
        # Read and print the updated config
        with open('/root/node_identity.json', 'r') as f:
            updated_config = json.load(f)
            debug_print("\n=== Final Configuration ===")
            debug_print(json.dumps(updated_config, indent=2))
            print(json.dumps(updated_config, indent=4))
            
    except Exception as e:
        debug_print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 