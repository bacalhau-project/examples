
# DDW - Distributed Data Warehouse client 

DDW is a Python application which simplifies writing queries to run on data that is stored locally to Bacalhau compute nodes.

By settings up a simple configuration file, you can quickly get to writing SQL queries against the data and seeing the results immediately, or having them merged into a single CSV file for processing in Excel. 

## Installation

[Poetry](https://python-poetry.org/) is required to install this application.  After following [the installation instructions](https://python-poetry.org/docs/#installation), you can run the following in the current directory to install DDW.

```
poetry install
```

## Configuration

To get started, you should copy the file `config.yaml.sample` to `config.yaml` and change the necessary values within it. 

Typically this will be the IP address of your Bacalhau cluster, and the S3 bucket name that you have credentials for (both in the cluster and locally). Depending on where your compute nodes are obtaining their data from (any format supported by DuckDB) you may need to modify the settings in the `input` section.

## Command line flags 

The program has various command line flags that you can see by using 

```shell
poetry run ddw --help
```

The key options are:

 -c CONFIG, --config CONFIG
                        Specify a config file, default: config.yaml
  -s KEY=VALUE, --select KEY=VALUE
                        Specify what nodes to run the query on
  -a, --all             Run on all matching nodes
  -p, --print           Print output to stdout

## Running Queries 

To run a simple query on any node you can the following and see the output on the command line.

```shell
poetry run ddw -p "SELECT COUNT(*) from '/inputs/trxn.csv'"
```

To run the same query on all of the nodes in the cluster, you can use `-a` as follows and you will get N sets of results shown, depending on the size of the cluster.

```shell
poetry run ddw -a -p "SELECT COUNT(*) from '/inputs/trxn.csv'"
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
-s region=EU     # A single node in the EU region
-a -s region=EU  # All nodes in the EU region
-a -s city=Paris # All nodes in the city of Paris 
-a               # All nodes in the entire cluster
```

Extending our query from earlier, the count of transactions in our EU region is as follows

```shell
$ poetry run ddw -p -a -s region=EU "SELECT COUNT(*) as Total FROM '/inputs/trxn.csv'"
Submitted job: 12d16f92-652f-48a6-8eb0-9983e5015cda

Execution: e-59eae330-1717-4f82-877a-d2386b122e24
Total
355791

Execution: e-bf002504-2781-4e42-adf3-d94ebff193f7
Total
355790
```

If we want the answers in a single file, we can remove the `-p` to get them in a single CSV file.

```shell
$ poetry run ddw -a -s region=EU "SELECT COUNT(*) as Total FROM '/inputs/trxn.csv'"
Submitted job: 89182f0b-8953-46dc-8c38-649132c7a05f
Output written to: output-89182f0b.csv
```