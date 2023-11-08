# Query Server

Query server provides a service for the mycelial demo where when given a sentence, will do a similarity search to find a sentence that we have a known query for.  In addition it will then extract any numbers in submission for use in the query.

## Configuration


* Install Python > 3.8
* Install Poetry
* Clone this repo
* `poetry install``
* Create a queries file (see below)
* Create an outputs directory (mkdir outputs/)
* `poetry run models` to install the required models

## The queries file

This should be a JSON file in the following format.

```json
[
    {
        "sentence": [
            "show me when engine 2 last went above 100"
        ],
        "query": "SELECT Engine, Thrust, Temperature FROM engine_data where engine=? and temperature > ?"
    }
]
```

More than one sentence can be provided that will match the query. In this example we expect the response to be

{
    "query": "SELECT Engine, Thrust, Temperature FROM engine_data where engine=? and temperature > ?",
    "replacements": ["2", "100"]
}


## Running the server

You can run the server with the following:

```shell
poetry run server -d <QUERIES.JSON> -o <OUTPUT_DIR> -l <LIMIT>
```

* -d specifies the location of the queries file
* -o the location of the outputs directory
* -l the lower limits for the similarity score, aim for 0.7 - 0.8. Default is 0.5


## Docker image

You can use the dockerfile to build a docker image of this code with.

`docker build myusername/myimagename:0.0.1 .`

To run the docker image with the queries.json and outputs folder both in the current directory, you can use:

```
docker run -it \
    -v .:/mnt \
    -p 2112:2112 \ 
    rossjones73/qserver:0.0.1 \
    poetry serve -d /mnt/queries.json -o /mnt/outputs -l 0.7
```