import json
import os
from datetime import datetime
import duckdb
import tempfile
import argparse
import requests
from natsort import natsorted, ns
from google.cloud import storage


def getInstanceMetadata(metadataName):
    url = f"http://metadata.google.internal/computeMetadata/v1/instance/{metadataName}"
    return getMetadata(url)


def getProjectMetadata(metadataName):
    url = f"http://metadata.google.internal/computeMetadata/v1/project/{metadataName}"
    return getMetadata(url)


def getMetadata(metadata_server_url):
    metadata_server_token_url = "http://metadata/computeMetadata/v1/instance/service-accounts/default/token"
    token_request_headers = {"Metadata-Flavor": "Google"}
    token_response = requests.get(metadata_server_token_url, headers=token_request_headers)
    jwt = token_response.json()["access_token"]

    metadata_request_headers = {"Metadata-Flavor": "Google", "Authorization": f"Bearer {jwt}"}

    return requests.get(metadata_server_url, headers=metadata_request_headers).text


def main(input_file, query):
    # Create an in-memory DuckDB database
    con = duckdb.connect(database=":memory:", read_only=False)

    usingTempFile = False
    # If file is .gz, decompress it into a temporary file
    if input_file.endswith(".gz"):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as temp:
            os.system(f"gunzip -c {input_file} > {temp.name}")
            input_file = temp.name
            usingTempFile = True

    # Create a table from the JSON data
    con.execute(
        "CREATE TABLE log_data AS SELECT * FROM read_json(?, "
        "auto_detect=true,"
        f"columns={json.dumps({'id': 'varchar', '@timestamp': 'varchar', '@version': 'varchar', 'message': 'varchar'})})",
        [input_file],
    )

    # Execute the DuckDB query on the log data
    # SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY \"@timestamp\"
    result = con.execute(query).fetchdf()

    # Convert the result to JSON
    result_json = result.to_json(orient="records")

    # Generate the output file name
    output_file_name = f"{getInstanceMetadata('name')}-{datetime.now().strftime('%Y%m%d%H%M')}.json"

    # Get the region from the metadata server
    region = getInstanceMetadata("zone").split("/")[3]
    projectID = getProjectMetadata("project-id")

    # Generate the bucket name
    bucket_name = f"{projectID}-{region}-archive-bucket"

    print("Bucket name: gs://" + bucket_name + "\n")

    # Write the result to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as temp:
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

    if usingTempFile:
        os.remove(input_file)


if __name__ == "__main__":
    # Print a header to a list of files that are available to process
    print("Files available to process (in /var/log/logs_to_process):")
    print("--------------------")

    # Print all files in /var/log/logs_to_process to stdout with absolute paths.
    # If there are no files, print a message that "No files are available to process."
    files = os.listdir("/var/log/logs_to_process")
    if len(files) == 0:
        print("No files are available to process.")
    else:
        f = natsorted(files, alg=ns.IGNORECASE)
        for file in f:
            print(f"/var/log/logs_to_process/{file}")

    print("\n")

    print("Environment Variables")
    print(f"INPUTFILE = {os.environ.get('INPUTFILE')}")
    print(f"QUERY = {os.environ.get('QUERY')}")

    # If both INPUTFILE and QUERY are set, then use those
    if os.environ.get("INPUTFILE") and os.environ.get("QUERY"):
        print("Both INPUTFILE and QUERY are set, so using those")
        args = argparse.Namespace(input_file=os.environ.get("INPUTFILE"), query=os.environ.get("QUERY"))
    else:
        # Set up the argument parser
        parser = argparse.ArgumentParser(description="Process log data")
        parser.add_argument("input_file", help="Path to the input log file")
        parser.add_argument("query", help="DuckDB query to execute")

        # Parse the command-line arguments
        args = parser.parse_args()

    # Call the main function
    main(args.input_file, args.query)
