#!/usr/bin/env bash
set -e
set -x

python -m pip install poetry # Install poetry in the newly created virtual environment

# If $APPDIR does not exist then create it
if [ ! -d "$APPDIR" ]; then
    mkdir -p $APPDIR
fi

cd $APPDIR || exit

# If pyproject.toml isn't there then copy the app files from /tmp
if [ ! -f "pyproject.toml" ]; then
    rsync -av --exclude '\.*' --exclude "__*" /tmp/client/* $APPDIR # APPDIR has a leading /
fi

python -m pip install poetry-plugin-export
python -m poetry export --without-hashes --format=requirements.txt > requirements.txt
python -m pip  install virtualenv
python -m venv ${PYENVNAME}
# shellcheck source=/dev/null
source ${PYENVNAME}/bin/activate

# Install all python requirements from requirements.txt
python -m pip install -r requirements.txt

deactivate
