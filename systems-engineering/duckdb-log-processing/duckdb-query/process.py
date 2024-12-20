import argparse
import json
import os
import tempfile
from datetime import datetime

import duckdb
import requests
from google.cloud import storage
from natsort import natsorted, ns


def getFakeMetadata():
    return {
        "name": "local-instance",
        "zone": "projects/local-project/zones/local-zone",
        "project-id": "local-project",
    }


def getInstanceMetadata(metadataName):
    if os.environ.get("LOCAL_MODE"):
        return getFakeMetadata().get(metadataName, "local-" + metadataName)
    url = f"http://metadata.google.internal/computeMetadata/v1/instance/{metadataName}"
    return getMetadata(url)


def getProjectMetadata(metadataName):
    if os.environ.get("LOCAL_MODE"):
        return getFakeMetadata().get(metadataName, "local-" + metadataName)
    url = f"http://metadata.google.internal/computeMetadata/v1/project/{metadataName}"
    return getMetadata(url)


def getMetadata(metadata_server_url):
    metadata_server_token_url = (
        "http://metadata/computeMetadata/v1/instance/service-accounts/default/token"
    )
    token_request_headers = {"Metadata-Flavor": "Google"}
    token_response = requests.get(
        metadata_server_token_url, headers=token_request_headers
    )
    jwt = token_response.json()["access_token"]

    metadata_request_headers = {
        "Metadata-Flavor": "Google",
        "Authorization": f"Bearer {jwt}",
    }

    return requests.get(metadata_server_url, headers=metadata_request_headers).text


def get_input_dir():
    """Get the input directory, allowing override via environment variable."""
    return os.environ.get("INPUT_DIR", "/var/log/logs_to_process")


def get_sorted_files():
    """Get a sorted list of files in the logs directory."""
    input_dir = get_input_dir()
    if not os.path.exists(input_dir):
        print(f"Warning: Input directory {input_dir} does not exist")
        return []
    files = os.listdir(input_dir)
    return natsorted(files, alg=ns.IGNORECASE)


def process_files(files_to_process, query):
    """Process one or more files with the given query."""
    # Create an in-memory DuckDB database
    con = duckdb.connect(database=":memory:", read_only=False)
    temp_files = []

    con.execute("SET order_by_non_integer_literal=true")
    
    try:
        # First, create the table structure
        con.execute("""
            CREATE TABLE IF NOT EXISTS log_data (
                id VARCHAR,
                "@timestamp" VARCHAR,
                "@version" VARCHAR,
                message VARCHAR
            )
        """)

        # Process each input file
        for input_file in files_to_process:
            input_dir = get_input_dir()
            full_path = os.path.join(input_dir, input_file)

            print(f"Processing file: {full_path}")

            # If file is .gz, decompress it into a temporary file
            if full_path.endswith(".gz"):
                with tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".log"
                ) as temp:
                    os.system(f"gunzip -c {full_path} > {temp.name}")
                    full_path = temp.name
                    temp_files.append(temp.name)

            # Insert data from the JSON file
            con.execute(
                """
                INSERT INTO log_data 
                SELECT * FROM read_json(?, 
                    auto_detect=true,
                    columns={"id": "varchar", 
                    "@timestamp": "varchar", 
                    "@version": "varchar", 
                    "message": "varchar"})
                """,
                [full_path],
            )

            print("Debug: First few rows of data:")
            debug_result = con.execute("SELECT * FROM log_data LIMIT 5").fetchdf()
            print(debug_result)

        result = con.execute(query).fetchdf()

        # Convert the result to JSON
        result_json = result.to_json(orient="records")

        # If in local mode, just print to stdout and return
        if os.environ.get("LOCAL_MODE"):
            print(result_json)
            return

        # Generate the output file name
        output_file_name = f"{getInstanceMetadata('name')}-{datetime.now().strftime('%Y%m%d%H%M')}.json"

        # Get the region from the metadata server
        region = getInstanceMetadata("zone").split("/")[3]
        projectID = getProjectMetadata("project-id")

        # Generate the bucket name
        bucket_name = f"{projectID}-{region}-archive-bucket"

        print("Bucket name: gs://" + bucket_name + "\n")

        # Write the result to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp:
            temp.write(result_json)
            temp.close()

            # Upload the file to GCP bucket
            storage_client = storage.Client()
            bucket = storage_client.get_bucket(bucket_name)
            blob = bucket.blob(output_file_name)
            blob.upload_from_filename(temp.name)

            # Upload the file to the global bucket
            global_bucket_name = f"{projectID}-global-archive-bucket"
            global_bucket = storage_client.get_bucket(global_bucket_name)
            global_blob = global_bucket.blob(output_file_name)
            global_blob.upload_from_filename(temp.name)

            # Remove the temporary file
            os.remove(temp.name)

        outputJSON = {f"{bucket_name}": result.to_json(orient="records")}
        print(outputJSON)

    finally:
        # Clean up any temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except OSError:
                pass


if __name__ == "__main__":
    input_dir = get_input_dir()
    print("Files available to process in:", input_dir)
    print("--------------------")

    # Get sorted list of files
    files = get_sorted_files()
    if len(files) == 0:
        print("No files are available to process.")
        exit(1)
    else:
        for file in files:
            print(os.path.join(input_dir, file))

    print("\n")

    print("Environment Variables")
    print(
        f"INPUT_DIR = {os.environ.get('INPUT_DIR', '/var/log/logs_to_process')} (default: /var/log/logs_to_process)"
    )
    print(f"INPUTFILE = {os.environ.get('INPUTFILE')}")
    print(f"QUERY = {os.environ.get('QUERY')}")

    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument(
        "--local", action="store_true", help="Run in local mode without GCP integration"
    )
    parser.add_argument(
        "--all", action="store_true", help="Process all files in the directory"
    )
    parser.add_argument(
        "--latest", action="store_true", help="Process only the latest file"
    )
    parser.add_argument("input_file", nargs="?", help="Path to the input log file")
    parser.add_argument("query", nargs="?", help="DuckDB query to execute")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Set local mode if --local flag is used
    if args.local:
        os.environ["LOCAL_MODE"] = "true"

    # Determine which files to process
    if os.environ.get("INPUTFILE"):
        print("Using INPUTFILE from environment")
        files_to_process = [os.environ.get("INPUTFILE")]
    elif args.all:
        print("Processing all files in directory")
        files_to_process = files
    elif args.latest:
        print("Processing latest file")
        if not files:
            print("No files found in directory")
            exit(1)
        files_to_process = [files[-1]]
    elif args.input_file:
        files_to_process = [args.input_file]
    else:
        parser.error(
            "Must specify one of: --all, --latest, input_file, or INPUTFILE environment variable"
        )

    # Determine the query
    query = os.environ.get("QUERY")
    if not query and args.query:
        query = args.query
    if not query:
        parser.error(
            "Must specify query either through QUERY environment variable or as command line argument"
        )

    # Process the files
    process_files(files_to_process, query)
