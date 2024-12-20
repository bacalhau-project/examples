#!/usr/bin/env bash
set -e
set -x

# If PYENVNAME or APPDIR is not set, exit with error
if [ -z "${PYENVNAME}" ] || [ -z "${APPDIR}" ]; then
    echo "PYENVNAME or APPDIR is not set. Exiting."
    exit 1
fi

# Add .local/bin to PATH
export PATH="/home/${APPUSER}/.local/bin:${PATH}"

# Activate virtual environment
export PATH="${APPDIR}/${PYENVNAME}/bin:${PATH}"

# Global uv installation
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
export PATH="/home/${APPUSER}/.cargo/bin:${PATH}"
uv venv "${PYENVNAME}" --seed

# Use source directive to specify the location of the activation script
# Use a directive to specify the location of the activation script

# Install Python dependencies from requirements.txt
# shellcheck disable=SC1090
source "${APPDIR}/${PYENVNAME}/bin/activate"
pip install -r /tmp/requirements.txt

uv clean
