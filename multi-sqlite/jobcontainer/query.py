# Query local sqlite database for job information
import sqlite3
import argparse


def get_data(query):
    with sqlite3.connect("/node/sensor_data.db") as conn:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        return rows


def main():
    query = input("Enter a query: ")
    rows = get_data(query)
    for row in rows:
        print(row)


if __name__ == "__main__":
    # Print a header to a list of files that are available to process
    print("Tables to process")
    print("--------------------")

    # Get a list of all tables in SQLite database
    tables = get_data("SELECT name FROM sqlite_master WHERE type='table';")

    if len(tables) == 0:
        print("No tables are available to process.")
    else:
        for t in tables:
            print(f"{t}")

    print("\n")

    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Process SQLite database")
    parser.add_argument("query", help="Query to execute")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the main function
    main(args.query)
