#!/usr/bin/env bash
set -e
set -x

# Clean up old files, just to be sure
export USERHOME="/home/${APPUSER}"
export PATH="${USERHOME}/.local/bin:${PATH}"
export SETUPVENVSCRIPT="${USERHOME}/setup-venv.sh"

echo "USERHOME: ${USERHOME}"
echo "APPUSER: ${APPUSER}"
echo "APPDIR: ${APPDIR}"
echo "PATH: ${PATH}"

echo "Runnig setup-venv.sh ..."
pushd "${APPDIR}"
chown -R "${APPUSER}":"${APPUSER}" "${SETUPVENVSCRIPT}"
sudo -E -u "${APPUSER}" bash -c "source ${ENVFILE} && ${SETUPVENVSCRIPT}"
popd