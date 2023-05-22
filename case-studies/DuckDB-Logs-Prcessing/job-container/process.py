import json
import os
from datetime import datetime
import duckdb
import tempfile
import argparse
import requests
import pandas as pd
from google.cloud import storage

def get_metadata(metadata_name):
    metadata_server_token_url = "http://metadata/computeMetadata/v1/instance/service-accounts/default/token"
    token_request_headers = {'Metadata-Flavor': 'Google'}
    token_response = requests.get(metadata_server_token_url, headers=token_request_headers)
    jwt = token_response.json()['access_token']

    metadata_server_url = f"http://metadata.google.internal/computeMetadata/v1/instance/{metadata_name}"
    metadata_request_headers = {'Metadata-Flavor': 'Google', 'Authorization': f'Bearer {jwt}'}

    return requests.get(metadata_server_url, headers=metadata_request_headers).text

def main(input_file):
    # Create an in-memory DuckDB database
    con = duckdb.connect(database=':memory:', read_only=False)

    # Create a table from the JSON data
    con.execute(f"CREATE TABLE log_data AS SELECT * FROM read_json('{input_file}', "
                f"auto_detect=false, "
                f"columns={json.dumps({'id': 'varchar', '@timestamp': 'varchar', '@version': 'varchar', 'message': 'varchar'})})")

    # Execute the DuckDB query on the log data
    result = con.execute("SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY \"@timestamp\"").fetchdf()

    # Convert the result to JSON
    result_json = result.to_json(orient='records')

    # Generate the output file name
    output_file_name = f"{get_metadata('name')}-Security-{datetime.now().strftime('%Y%m%d%H%M')}.json"

    # Get the region from the metadata server
    region = get_metadata("zone").split("/")[3]

    # Generate the bucket name
    bucket_name = f"{region}-node-archive-bucket"

    # Write the result to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp:
        temp.write(result_json)
        temp.close()

        # Upload the file to GCP bucket
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(output_file_name)
        blob.upload_from_filename(temp.name)

        # Remove the temporary file
        os.remove(temp.name)

if __name__ == "__main__":
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the main function
    main(args.input_file)