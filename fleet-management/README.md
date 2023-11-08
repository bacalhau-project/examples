
# query-cluster

query-cluster is a Python application which invokes osquery on the Bacalhau compute nodes, and combines the results into a single JSON file.

## Installation

[Poetry](https://python-poetry.org/) is required to install this application.  After following [the installation instructions](https://python-poetry.org/docs/#installation), you can run the following in the current directory to install DDW.

```
poetry install
```

## Configuration

To get started, you should copy the file `config.yaml.sample` to `config.yaml` and change the necessary values within it. 

Typically this will be the IP address of your Bacalhau cluster, and the S3 bucket name that you have credentials for (both in the cluster and locally).

## Command line flags 

The program has various command line flags that you can see by using 

```shell
poetry run ddw --help
```

The key options are:

 -c CONFIG, --config CONFIG
                        Specify a config file, default: config.yaml
  -s KEY=VALUE, --select KEY=VALUE
                        Specify what nodes to run the query on (defaults to all)
  -p, --print           Print output to stdout

## Running Queries

To run a simple query on any node you can the following and see the output on the command line.

```shell
poetry run query-cluster -p "select hostname from system_info"
```

If you wish to only run nodes on a subset of the cluster, you can use `-s` to specify the criteria for the nodes on which the query should run.  

Given a set of compute nodes with the following labels:

|Node|Labels|
|--|--|
|1|region=EU, country=FR, city=Paris|
|1|region=EU, country=DE, city=Berlin|
|1|region=NorthAmerica, country=US, city=Washington|
|1|region=NorthAmerica, country=CA, city=Toronto|

You can use the selectors as follows:

```
-s region=EU  # All nodes in the EU region
-s city=Paris # All nodes in the city of Paris
```

Let's see if any of our nodes in the EU are running out of disk space in their root partitions:

```shell
$ poetry run query-cluster -p -s region=EU "select blocks_free*blocks_size/1048576 as megbytes_free from mounts where path='/'"
Submitted job: 22ce32fe-5dd5-43de-b3ed-16e657dc2f02
[
{"megbytes_free": "42387", "nodeID": "QmeD1rESiDtdVTDgekXAmDDqgN9ZdUHGGuMAC77krBGqSv"},
{"megbytes_free": "39608", "nodeID": "QmfKmkipkbAQu3ddChL4sLdjjcqifWQzURCin2QKUzovex"}
]
```

If we want the answers in a single file, we can remove the `-p` to get them in a single JSON file.

```shell
$ poetry run ddw -a -s region=EU "SELECT COUNT(*) as Total FROM '/inputs/trxn.csv'"
Submitted job: 31b847a0-44d2-4cf5-8630-01b5a2d6cee3
Output written to: output-31b847a0.json
```
