# Mycelial / Bacalhau integration demo

This directory contains components necessary for building a demonstration of the integration between [Mycelial](https://www.mycelial.com/) and [Bacalhau](https://www.bacalhau.org/).

The integration results in a REPL where a user can enter a question. The questions is written to a local database which is connected to a Mycelial node.  Mycelial then moves the data across, through a mycelial node that communicates with Bacalhau, and then into another database.  The REPL then picks up the answers from the second (answers) database.

```
   ┌────────────────────────┐         ┌────────────────────────┐
   │                        │         │                        │
   │  User writes query in  │         │     SQLite DB          │
   │      CLI/REPL          │◀────────│     answers.sqlite     │
   │                        │         │                        │
   └────────────────────────┘         └────────────────────────┘
                │                                  ▲
                │                                  │
                │                                  │
                ▼                                  │
   ┌────────────────────────┐         ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
   │                        │                                  │
   │     SQLite DB          │         │   Mycelial sqlite
   │     questions.sqlite   │             connector            │
   │                        │         │
   └────────────────────────┘          ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                ▲                                  ▲
                │                                  │
                │                                  │
   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─          ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                            │                                  │
   │   Mycelial sqlite                │    Bacalhau LLM
       connector            │────────▶       on Mycelial       │
   │                                  │
    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘          ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

## Installing components

**Mycelial**

Current release 0.1.3

* Server -> [server-*.tgz](https://github.com/mycelial/mycelial/releases/tag/v0.1.3)
* Client -> [myceliald-*.tgz](https://github.com/mycelial/mycelial/releases/tag/v0.1.3)

**Test server**

* Install Python >= 3.9
* Copy server.py from ./test-server into a folder 
* Open terminal in folder
* `mkdir ./outputs`
* `./server.py`


**REPL** 

* Follow instructions in [demo-client README](./demo-client/README.md). 
* Note: you cannot configure the config.yaml until you have performed the configuration steps below.


**Data-gen**

Data generator for demo

* Follow instructions in [data-gen README](./data-gen/README.md). 

## Configuration / Setup 

* Create a directory on disk, referred to as $DIR in rest of instructions.
* `touch $DIR/questions.db`
* `touch $DIR/answers.db`
* Update demo-client's config.yaml to use absolute paths to point to these two files.
* Create a `config.toml` and add the following *making sure to change the database paths*.

```toml
[node]
display_name = "Node 1"
unique_id = "node1"
storage_path = "node1.sqlite"

[server]
endpoint = "http://localhost:8080"
token = "token"

[[sources]]
type = "sqlite_connector"
display_name = "Questions DB"
path = "PATH TO QUESTIONS DATABASE"

[[destinations]]
type = "sqlite_connector"
display_name = "Answers database"
path = "PATH TO ANSWERS DATABASE"
tables = "questions"
```

* Run mycelial server in a terminal, `server -t token -d mycelial.db`. The database will be created by the server. 
* Run mycelial client in a terminal, pointing to this toml file. `myceliald -c config.toml`
* Visit http://127.0.0.1:8080 and add a sqlconnector source, a bacalhau node and then another sqlconnector. Make sure the outputs folder of bacalhau node points to the test-server's output directory. 

## Running a query.

Go to where you installed the llmclient, and run 

```shell
$ poetry run llmc
```

When you add a question to the repl, you should see a Waiting spinner whilst the query is processing.  If you are running the test-server, you should see output suggesting it received a message and then your answer should appear in the REPL.  If you are using the test-server, the answer should be the original message in upper case and reversed.

## Running an LLM in Bacalhau 

TODO