#!/bin/sh

# This script disables the execution of all cells in a notebook.

if [ $# -ne 1 ]; then
    echo "Usage: disable_execution.sh notebook.ipynb"
    exit 1
fi

if ! command -v jq &> /dev/null
then
    echo "jq could not be found, please install"
    exit
fi


tmpfile=$(mktemp)
jq '.cells[].metadata += {"tags": ["skip-execution"]}' $1 > tmpfile && mv tmpfile $1