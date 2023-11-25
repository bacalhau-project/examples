# Mycelial integration demo - Execution

This repository contains the code, config and information required to run a mycelial execution demo (on Windows). Steps for running on Linux/OSX not provided, but it should be possible to intuit them from these instructions.  

The demonstration shows a Bacalhau destination node receiving arrow messages about a newly downloaded zip file.  On receipt of the message, the node will retrieve the job spec configured for that node, and interpolate the arrow message with the contents of the spec.  This specification will then be sent to a local Bacalhau instance for execution.  The values interpolated are expected to be values that are passed through to the executor, in this case, a raw process executor. 

```
┌ ─ ─ ─ ─ ─ ─ ─ 2
      HTTP       
└ ─ ─ ─ ─ ─ ─ ─ ┘
        ▲        
        │        
        │        
 ┌─────────────1           ┌───────────4                         
 │  Download   │           │ Bacalhau  │                         
 │   Source    │───msg────▶│ mycelial  │                         
 │             │           │   node    │                         
 └─────────────┘           └───────────┘                         
        │                        │                               
                                API                              
        │                        │                               
                                 ▼                               
        │                 ┌────────────5                         
                          │  Bacalhau  │                         
        │                 └────────────┘                         
                                 │                               
        ▼                        ▼            ┌ ─ ─ ─ ─ ─ ─ ─ ─ 7
┌ ─ ─ ─ ─ ─ ─ ─ 3         ┌────────────6            Extract  
  Write to disk  ────────▶│  Executor  │─────▶│    multiple     │
└ ─ ─ ─ ─ ─ ─ ─ ┘         └────────────┘            files             
                                              └ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

## Contents 

The various directories hold the component parts necessary to compose a demonstration on a Window server.

_dependencies.ps1_ - a powershell script containing commands that will fetch the appropriate versions of tools needed to build the demo (go, rust, make etc).

_build.bat_ - this file will check for installed dependencies and then download the two branches (bacalhau and mycelial) to be compiled into ./build.

### bin 

This directory is currently a placeholder that _may_ end up holding specifically pre-compiled versions of the various services.

### build 

Currently empty, but will hold the repository code after `build.bat` has been run. 

### config 

_myceliald.config.toml_ - contains the configuration (with defaults) for the mycelial nodes required for the demo.

_start_bacalhau_node.bat_ - A simple 'shell' script to run a bacalhau hybrid note. Intended to be run as part of a service (via nssm). 


### jobstore 

Contains the job specifications for an `extract` and an `aggregate` job.  These are templates used by mycelial to define a configurable job. 

_extract.yml_ - Extracts files from a zip file into the specified folder. The location of the zip file is configurable. 

_aggregate.yml_ - Extracts data from the previously unpacked files and processes them. 

### scripts 

Contains the python scripts used by both the extract and aggregate job. These must be pre-installed as per the jobstore specs (e.g. in a specific location where bacalhau's executor can find them).

----

## TODO:

* Code: Make the API call to bacalhau from mycelial 
* Missing dependencies for rust build (cmake, sqlx-cli etc)
* Installation/Setup of nssm for service manager 
* Find manual trigger to act as download source
* Run through end-to-end demo 

