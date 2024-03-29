#!/usr/bin/env bash

set -x

# Check to make sure uv is installed
# If not, install it
if ! command -v uv &> /dev/null
then
    echo "uv could not be found"
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PIP_REQUIRE_VIRTUALENV=true

# If current directory is not the root of the project, cd to it
if [ ! -f "Makefile" ]; then
    cd ..
fi

uv venv
source .venv/bin/activate
uv pip install poetry
uv pip install -r ./ops/requirements.txt
pre-commit install
