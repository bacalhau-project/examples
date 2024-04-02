#!/usr/bin/env bash
set -e
set -x

# Ensure poetry is installed
python -m pip install --user poetry

# If $APPDIR does not exist then create it
if [ ! -d "$APPDIR" ]; then
    mkdir -p "$APPDIR"
fi

cd "$APPDIR" || exit

# If pyproject.toml isn't there then copy the app files from /tmp

# Install poetry-plugin-export
python -m pip install --user poetry-plugin-export

# Export dependencies to requirements.txt
python -m poetry export --without-hashes --format=requirements.txt > requirements.txt

# Install virtualenv
python -m pip install --user virtualenv

# Create and activate virtual environment
python -m venv "${PYENVNAME}"
source "${PYENVNAME}/bin/activate"

# Install Python dependencies from requirements.txt
python -m pip install -r requirements.txt

# Deactivate virtual environment
deactivate
