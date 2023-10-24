# LLM Client for Mycelial/Bacalhau

This application acts as a simple client for the Mycelial/Bacalhau integration demo.  It provides a __very__ simple repo which writes data to a local sqlite database, and then polls for the result in the answers database.  The answers database will have been populated by a Mycelial pipeline that runs:

```
SQLite --> Bacalhau --> SQLite
              \
               --> LLM
```

## Installation

* Install Python > 3.8
* Install [Poetry](https://python-poetry.org/)
* Clone this repo
* `poetry install`
* Copy config.sample.yaml to config.yaml
* Edit config.yaml to point to your two file 

## Running the script

```shell
$ poetry run llmclient 
```

Type messages, get replies.
`.q` to exit.

