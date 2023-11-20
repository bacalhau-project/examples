#!/bin/bash

# This is helper script to set environment variables and fetch secret values from CDK outputs file.
# The purpose is help users set their environments to work with the sample jobs in this example, and
# to fetch the OpenSearch password from Secrets Manager.
#
# Usage:
# helper.sh setenv # print environment variables
# helper.sh dashboard_password # print OpenSearch password
# source helper.sh setenv # Set environment variables


# Function to set environment variables
setEnvironmentVariables() {
    BACALHAU_NODE_CLIENTAPI_HOST=$(jq -r '.BacalhauLogOrchestration.OrchestratorPublicIp' <<< "$json")
    ResultsBucket=$(jq -r '.BacalhauLogOrchestration.ResultsBucketName' <<< "$json")
    AccessLogBucket=$(jq -r '.BacalhauLogOrchestration.AccessLogBucketName' <<< "$json")
    OpenSearchEndpoint=$(jq -r '.BacalhauLogOrchestration.OpenSearchEndpoint' <<< "$json")
    AWSRegion=$(jq -r '.BacalhauLogOrchestration.AWSRegion' <<< "$json")

    # Export and echo the variables
    export BACALHAU_NODE_CLIENTAPI_HOST
    echo "export BACALHAU_NODE_CLIENTAPI_HOST=$BACALHAU_NODE_CLIENTAPI_HOST"

    export ResultsBucket
    echo "export ResultsBucket=$ResultsBucket"

    export AccessLogBucket
    echo "export AccessLogBucket=$AccessLogBucket"

    export OpenSearchEndpoint
    echo "export OpenSearchEndpoint=$OpenSearchEndpoint"

    export AWSRegion
    echo "export AWSRegion=$AWSRegion"
}

# Function to fetch secret value
fetchSecretValue() {
    open_search_password_retriever=$(jq -r '.BacalhauLogOrchestration.OpenSearchPasswordRetriever' <<< "$json")
    if [ -n "$open_search_password_retriever" ]; then
        secret_response=$($open_search_password_retriever)
        echo "Fetched OpenSearch password: $secret_response"
    fi
}

# cdk outputs file
json_file="outputs.json"

# Check if the JSON file exists
if [ ! -f "$json_file" ]; then
    echo "Error: '$json_file' not found."
    echo "Please ensure that '$json_file' is in the current directory or specify the correct path."
    echo "To generate this file, run your CDK deployment with --outputs-file $json_file:"
    return 1
fi

# Read JSON file
json=$(cat "$json_file")

# Check command-line arguments
case "$1" in
    setenv)
        setEnvironmentVariables
        ;;
    dashboard_password)
        fetchSecretValue
        ;;
    *)
        echo "Usage: $0 {setenv|dashboard_password}"
        return 1
        ;;
esac