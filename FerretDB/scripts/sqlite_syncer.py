#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pymongo"
# ]
# ///

#
# Script that transfer all data points to FerretDB
#

import os
import sqlite3
from pymongo import MongoClient

def fetch_and_sync():
    conn = sqlite3.connect("/app/data/sensor_data.db")
    cursor = conn.cursor()

    try:
        # Fetch rows where synced is 0
        cursor.execute("SELECT * FROM sensor_readings WHERE synced=0")
        rows = cursor.fetchall()

        if not rows:
            print("No unsynced records found.")
            return

        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI", "")
        database_name = os.getenv("DATABASE_NAME", "postgres")
        collection_name = os.getenv("COLLECTION_NAME", "sensor_readings")

        client = MongoClient(mongodb_uri)
        db = client[database_name]
        collection = db[collection_name]

        # Prepare documents for batch insertion
        documents = []
        batch_size = 100  # You can adjust the batch size as needed

        for row in rows:
            doc = dict(zip([column[0] for column in cursor.description], row))
            documents.append(doc)

        # Insert documents in batches
        total_inserted = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            result = collection.insert_many(batch)
            total_inserted += len(result.inserted_ids)

        print(f"Inserted {total_inserted} records into MongoDB.")

        # Mark the records as synced
        for row in rows:
            cursor.execute("UPDATE sensor_readings SET synced=1 WHERE id=?", (row[0],))

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Commit changes and close connections
        conn.commit()
        conn.close()

if __name__ == "__main__":
    fetch_and_sync()
