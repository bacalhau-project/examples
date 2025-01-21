#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
# ]
# ///

import os

import duckdb


def print_query_results(query, title="Query Results"):
    print(f"\n{title}:")
    print("-" * 80)
    print(f"Query: {query}")
    print("-" * 80)
    result = con.execute(query).fetchall()
    for row in result:
        print(row)
    print("-" * 80)


# Connect to DuckDB
con = duckdb.connect(database=":memory:")

# Create a table from the log file with proper NCSA format parsing
print("Reading access.log file...")
con.execute("""
    CREATE TABLE access_logs AS 
    SELECT 
        column0 as ip,
        column2 as user_id,
        SUBSTRING(column3, 2) as timestamp,
        SUBSTRING(column5, 2) as request,
        column6 as status_code,
        column7 as bytes,
        SUBSTRING(column8, 2, LENGTH(column8)-2) as referrer,
        SUBSTRING(column9, 2, LENGTH(column9)-3) as user_agent
    FROM read_csv_auto('access.log', 
                      delim=' ',
                      header=False,
                      filename=True,
                      skip=0)
""")

# Sample queries to test the logs
print_query_results(
    """
    SELECT COUNT(*) as total_requests 
    FROM access_logs
""",
    "Total Requests",
)

print_query_results(
    """
    SELECT 
        timestamp,
        COUNT(*) as requests
    FROM access_logs 
    GROUP BY timestamp 
    ORDER BY requests DESC 
    LIMIT 5
""",
    "Top 5 Busiest Times",
)

print_query_results(
    """
    SELECT 
        status_code,
        COUNT(*) as count
    FROM access_logs 
    GROUP BY status_code 
    ORDER BY count DESC
""",
    "Status Code Distribution",
)

print_query_results(
    """
    SELECT 
        SPLIT_PART(request, ' ', 2) as path,
        COUNT(*) as hits
    FROM access_logs 
    GROUP BY path 
    ORDER BY hits DESC 
    LIMIT 10
""",
    "Top 10 Requested Paths",
)

if __name__ == "__main__":
    print("DuckDB Query Test Complete")
