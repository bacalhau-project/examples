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

    # If /etc/motherduck-key exists, then read it in and get the token
    if os.path.exists("/db/motherduck-key"):
        with open("/db/motherduck-key") as f:
            token = f.read().strip()
    else:
        raise Exception("No token found in /db/motherduck-key")

    mdConnect = duckdb.connect(f"md:?token={token}")
    print("Connected to MotherDuck")
    mdConnect.execute("CREATE SCHEMA IF NOT EXISTS logs")
    # Create a table in MotherDuck to store the log data with an autoincrementing ID
    mdConnect.execute(
        "CREATE TABLE IF NOT EXISTS logs.log_data (projectID VARCHAR, region VARCHAR, nodeName VARCHAR, syncTime VARCHAR, remote_log_id VARCHAR, timestamp VARCHAR, version VARCHAR, message VARCHAR)"
    )

    # Generate the output file name
    projectID = getProjectMetadata("project-id")
    region = getInstanceMetadata("zone").split("/")[3]
    nodeName = getInstanceMetadata("name")
    syncTime = datetime.now().strftime("%Y%m%d%H%M%S")

    columns = {"id": "varchar", "@timestamp": "varchar", "@version": "varchar", "message": "varchar"}

    # Create a table from the JSON data
    raw_query = f"""WITH log_data as (
                        SELECT '{projectID}', '{region}', '{nodeName}', '{syncTime}', 
                        * FROM read_json(?, auto_detect=true, columns={columns})
                    ) 
                    INSERT INTO logs.log_data {query}"""
    mdConnect.execute(query=raw_query, parameters=[input_file])

    # With logs as (
    #   SELECT * FROM read_json(...)
    # ) INSERT INTO motherduck.logs.log_data {query}


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
