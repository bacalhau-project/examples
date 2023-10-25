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
