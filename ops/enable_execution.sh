#!/bin/sh

# This script enables the execution of all cells in a notebook.

if [ $# -ne 1 ]; then
    echo "Usage: enable_execution.sh notebook.ipynb"
    exit 1
fi

if ! command -v jq &> /dev/null
then
    echo "jq could not be found, please install"
    exit
fi


tmpfile=$(mktemp)
jq 'del( .cells[].metadata.tags | .[]? | select(index("skip-execution")) )' $1 > tmpfile && mv tmpfile $1