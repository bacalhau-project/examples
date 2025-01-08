# Using Bacalhau with DuckDB

## Introduction

DuckDB is a relational table-oriented database management system and supports SQL queries for producing analytical results. It also comes with various features that are useful for data analytics.

DuckDB is suited for the following use cases:

- Processing and storing tabular datasets, e.g. from CSV or Parquet files
- Interactive data analysis, e.g. Joining & aggregate multiple large tables
- Concurrent large changes, to multiple large tables, e.g. appending rows, adding/removing/updating columns
- Large result set transfer to client

In this example tutorial, we will show how to use DuckDB with Bacalhau. The advantage of using DuckDB with Bacalhau is that you don’t need to install,  there is no need to download the datasets since the datasets are are already available on the server you are looking to run the query on.

## Prerequisites

To get started, you need to install the Bacalhau client, see more information [here](https://docs.bacalhau.org/getting-started/installation)

We will be using Bacalhau setup with the standard [setting up Bacalhau network](https://docs.bacalhau.org/getting-started/create-private-network)

We will also need to have a server with some data to run the query on. In this example, we will use a server with the Yellow Taxi Trips dataset. The dataset is hosted on the server in `/bacalhau_data/yellow_taxi_trips.parquet`.

:::info
If you do not already have this data on your server, you can download it using the scripts in the `prep_data` directory. The command to download the data is `./prep_data/run_download_jobs.sh`  - and you must have the `/bacalhau_data` directory on your server.
:::


## Running the Query

To submit a job, run the following Bacalhau command:

```bash
bacalhau docker run -e QUERY="select 1" docker.io/bacalhauproject/duckdb:latest
```

This is a simple query that will return a single row with a single column - but the query will be executed in DuckDB, on a remote server.

### Structure of the command

Let's look closely at the command above:

* `bacalhau docker run`: call to bacalhau 

* `-e QUERY="select 1"`: the query to execute

* `docker.io/bacalhauproject/duckdb:latest`: the name and the tag of the docker image we are using

When a job is submitted, Bacalhau runs the query in DuckDB, and returns the results to the client.

After we run it, when we `describe` the job, we can see the following in standard output:

```
Standard Output
┌───────┐
│   1   │
│ int32 │
├───────┤
│     1 │
└───────┘
```

## Running with a YAML file
What if you didn't want to run everything on the command line? You can use a YAML file to define the job. In `simple_query.sql`, we have a simple query that will return the number of rows in the dataset. 

```sql
-- simple_query.sql
SELECT COUNT(*) AS row_count FROM yellow_taxi_trips;
```

To run this query, we can use the following YAML file:
```YAML
Tasks:
  - Engine:
      Params:
        Image: docker.io/bacalhauproject/duckdb:latest
        WorkingDirectory: ""
        EnvironmentVariables:
          - QUERY=WITH yellow_taxi_trips AS (SELECT * FROM read_parquet('{{ .filename }}')) {{ .query }}
      Type: docker
    Name: duckdb-query-job
    InputSources:
      - Source:
          Type: "localDirectory"
          Params:
            SourcePath: "/bacalhau_data"
            ReadWrite: true
        Target: "/bacalhau_data"
    Publisher:
      Type: "local"
      Params:
        TargetPath: "/bacalhau_data"
    Network:
      Type: Full
    Resources:
      CPU: 2000m
      Memory: 2048Mi
    Timeouts: {}
Type: batch
Count: 1
```

Though this looks like a lot of code, it is actually quite simple. The `Tasks` section defines the task to run, and the `InputSources` section defines the input dataset. The `Publisher` section defines where the results will be published, and the `Resources` section defines the resources required for the job.

All the work is done in the environment variables, which are passed to the Docker image, and handed to DuckDB to execute the query.

To run this query, we can use the following command:

```bash
bacalhau job run duckdb_query_job.yaml --template-vars="filename=/bacalhau_data/yellow_tripdata_2020-02.parquet" --template-vars="QUERY=$(cat simple_query.sql)"
```

This breaks down into the following steps:

1. `bacalhau job run`: call to bacalhau
2. `duckdb_query_job.yaml`: the YAML file we are using
3. `--template-vars="filename=/bacalhau_data/yellow_tripdata_2020-02.parquet"`: the file to read
4. `--template-vars="QUERY=$(cat simple_query.sql)"`: the query to execute

When we run this, we get back the following simple output:

```
Standard Output
┌───────────┐
│ row_count │
│   int64   │
├───────────┤
│   6299367 │
└───────────┘
```

## More complex queries
Let's say we want to run a more complex query. In `window_query_simple.sql`, we have a query that will return the average number of rides per 5 minute interval.

```sql
-- window_query_simple.sql
SELECT
    DATE_TRUNC('hour', tpep_pickup_datetime) + INTERVAL (FLOOR(EXTRACT(MINUTE FROM tpep_pickup_datetime) / 5) * 5) MINUTE AS interval_start,
    COUNT(*) AS ride_count
FROM
    yellow_taxi_trips
GROUP BY
    interval_start
ORDER BY
    interval_start;
```

When we run this, we get back the following output:

```
┌─────────────────────┬────────────┐
│   interval_start    │ ride_count │
│      timestamp      │   int64    │
├─────────────────────┼────────────┤
│ 2008-12-31 22:20:00 │          1 │
│ 2008-12-31 23:00:00 │          1 │
│ 2008-12-31 23:05:00 │          1 │
│ 2008-12-31 23:10:00 │          1 │
│ 2008-12-31 23:15:00 │          1 │
│ 2008-12-31 23:30:00 │          1 │
│ 2009-01-01 00:00:00 │          3 │
│ 2009-01-01 00:05:00 │          3 │
│ 2009-01-01 00:15:00 │          1 │
│ 2009-01-01 00:40:00 │          1 │
│ 2009-01-01 01:15:00 │          1 │
│ 2009-01-01 01:20:00 │          1 │
│ 2009-01-01 01:35:00 │          1 │
│ 2009-01-01 01:40:00 │          1 │
│ 2009-01-01 02:00:00 │          2 │
│ 2009-01-01 02:15:00 │          1 │
│ 2009-01-01 04:05:00 │          1 │
│ 2009-01-01 04:15:00 │          2 │
│ 2009-01-01 04:45:00 │          1 │
│ 2009-01-01 06:30:00 │          1 │
│          ·          │          · │
│          ·          │          · │
│          ·          │          · │
│ 2020-03-05 12:15:00 │          1 │
```

:::warning
The sql file needs to be run in a single line, otherwise the line breaks will cause some issues with the templating. We're working on improving this!
:::

With this structure, you can now run virtually any query you want on remote servers, without ever having to download the data. Welcome to compute over data by Bacalhau!