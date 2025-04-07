#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pymongo"
# ]
# ///


#
# Script that deletes all data points from FerretDB
#

import os

from pymongo import MongoClient


def drop_collection():
    # Retrieve MongoDB connection details from environment variables
    mongodb_uri = os.getenv("MONGODB_URI", "")
    database_name = os.getenv("DATABASE_NAME", "postgres")
    collection_name = os.getenv("COLLECTION_NAME", "sensor_readings")

    try:
        # Connect to the MongoDB client
        client = MongoClient(mongodb_uri)
        db = client[database_name]
        collection = db[collection_name]

        # Drop the specified collection
        collection.drop()
        print(f"Collection '{collection_name}' in database '{database_name}' has been dropped.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    drop_collection()
