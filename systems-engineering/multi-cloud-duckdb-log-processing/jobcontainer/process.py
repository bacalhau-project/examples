import json
import os
from datetime import datetime
import duckdb
import tempfile
import argparse


def main(input_file, query, output_directory):
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
    result = con.execute(query).fetchdf()

    # Convert the result to JSON
    result_json = result.to_json(orient="records")

    # Generate the output file name
    output_file_name = f"{datetime.now().strftime('%Y%m%d%H%M')}.json"

    # Write the result to a local directory specified by the output_directory argument
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    with open(f"{output_directory}/{output_file_name}", "w") as outfile:
        outfile.write(result_json)

    print(f"Local file written to {output_directory}/{output_file_name}")

    if usingTempFile:
        os.remove(input_file)


if __name__ == "__main__":
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    parser.add_argument("query", help="DuckDB query to execute")
    parser.add_argument("--output_dir", default="/outputs", help="Directory to save the output JSON file")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the main function
    main(args.input_file, args.query, args.output_dir)