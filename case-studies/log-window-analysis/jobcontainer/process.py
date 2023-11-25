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


def main(input_file):
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
    mdConnect.execute("CREATE SCHEMA IF NOT EXISTS log_aggregation;")
    # Create a table in MotherDuck to store the log data with an autoincrementing ID
    mdConnect.execute(
        """CREATE TABLE IF NOT EXISTS logs.log_aggregation 
        (projectID VARCHAR, 
        region VARCHAR, 
        nodeName VARCHAR, 
        syncTime VARCHAR, 
        start_ts VARCHAR, 
        end_ts VARCHAR, 
        distinct_ips VARCHAR, 
        distinct_users VARCHAR,
        distinct_routes VARCHAR,
        min_sessions VARCHAR,
        avg_sessions VARCHAR,
        max_sessions VARCHAR)"""
    )

    # Generate the output file name
    projectID = getProjectMetadata("project-id")
    region = getInstanceMetadata("zone").split("/")[3]
    nodeName = getInstanceMetadata("name")
    syncTime = datetime.now().strftime("%Y%m%d%H%M%S")

    columns = {
        "projectID": "varchar",
        "region": "varchar",
        "nodeName": "varchar",
        "syncTime": "varchar",
        "start_ts": "varchar",
        "end_ts": "varchar",
        "distinct_ips": "varchar",
        "distinct_users": "varchar",
        "distinct_routes": "varchar",
        "min_sessions": "varchar",
        "avg_sessions": "varchar",
        "max_sessions": "varchar",
    }

    # Create a table from the JSON data
    raw_query = f"""
                        create temp table logs as 
                            from read_csv_auto('{input_file}', delim=' ')
                            select 
                                column0 as ip,
                                -- ignore column1, it's just a hyphen
                                column2 as user,
                                column3.replace('[','').replace(']','').strptime('%Y-%m-%dT%H:%M:%S.%f%z') as ts,
                                column4 as http_type,
                                column5 as route,
                                column6 as http_spec,
                                column7 as http_status,
                                column8 as value
                        ;
                        create temp table time_increments as 
                            from generate_series(date_trunc('hour', current_timestamp) - interval '1 year', date_trunc('hour', current_timestamp) + interval '1 year', interval '5 minutes' ) t(ts)
                            select
                                ts as start_ts,
                                ts + interval '5 minutes' as end_ts,
                            where
                                ts >= ((select min(ts) from logs) - interval '5 minutes')
                                and ts <= ((select max(ts) from logs) + interval '5 minutes')
                        ;
                        create temp table session_duration_and_count as 
                        with last_login as (
                            from logs
                            select 
                                *,
                                max(case when route = '/login' then ts end) over (partition by ip, user order by ts rows between unbounded preceding and current row) as last_login_ts,
                        )
                        from last_login
                        select
                            *,
                            -- Assuming the first event is always a login
                            max(ts) over (partition by ip, user, last_login_ts) as last_txn_ts,
                            last_txn_ts - last_login_ts as session_duration,
                            sum(case route
                                when '/login' then 1 
                                when '/logout' then -1
                                end) over (order by ts) as session_count,
                        ;
                        from session_duration_and_count;

                        INSERT INTO logs.log_aggregation (
                        from time_increments increments
                        left join session_duration_and_count sessions
                            on increments.start_ts <= sessions.ts
                            and increments.end_ts > sessions.ts
                        select
                            '{projectID}', '{region}', '{nodeName}', '{syncTime}'
                            start_ts,
                            end_ts,
                            count(distinct ip) as distinct_ips,
                            count(distinct user) as distinct_users,
                            count(distinct route) as distinct_routes,
                            min(coalesce(session_count, 0)) as min_sessions,
                            avg(coalesce(session_count, 0)) as avg_sessions,
                            max(coalesce(session_count, 0)) as max_sessions,
                            1
                        group by all
                        order by
                            start_ts
                            )"""

    mdConnect.execute(query=f"{raw_query}")


# With logs as (
#   SELECT * FROM read_json(...)
# ) INSERT INTO motherduck.logs.log_data {query}


if __name__ == "__main__":
    print("Environment Variables")
    print(f"INPUTFILE = {os.environ.get('INPUTFILE')}")

    # If both INPUTFILE and QUERY are set, then use those
    if os.environ.get("INPUTFILE"):
        print("INPUTFILE is set, so using those")
        args = argparse.Namespace(input_file=os.environ.get("INPUTFILE"))
    else:
        # Set up the argument parser
        parser = argparse.ArgumentParser(description="Process log data")
        parser.add_argument("input_file", help="Path to the input log file")

        # Parse the command-line arguments
        args = parser.parse_args()

    # Call the main function
    main(args.input_file)
