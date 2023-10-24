
# Test server

The test server mimics a long-running Bacalhau job. By default the server listens on 127.0.0.1, port 2112 and will accept POST requests for any path.  The expectation here is that the Mycelial Bacalhau destination section will post any messages it receives to this server. The Mycelial Bacalhau source section will monitor the for any files written before forwarding the contents through the pipeline.

When a POST request it made to the server, it will expect the request to contain a JSON body.  The JSON will be parsed and expected to have "id" and "message" keys. The value of the "message" key will be upper-cased and reversed, and the newly updated JSON will be written to a folder called "./outputs/" and named after the value of the "id" key.

Message accepted:

```json
{
    "id": "1",
    "message": "hello"
}
```

Message written to `./outputs/1.json`: 

```json
{
    "id": "1",
    "message": "OLLEH"
}
```


## Installation

This script has no external dependencies, you can copy the file into place and run the following to make the file executable:

```shell
chmod u+x server.py
```

## Running the server 

If you have followed the installation step, you can run the server using:

```shell
./server.py
```