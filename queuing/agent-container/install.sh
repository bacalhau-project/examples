#!/usr/bin/env bash

# Ignore SC2317 for the entire file
# shellcheck disable=SC2317

# Bacalhau authors (c)

# Original copyright
# https://raw.githubusercontent.com/SAME-Project/SAME-installer-website/main/install_script.sh
# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation and Dapr Contributors.
# Licensed under the MIT License.
# ------------------------------------------------------------

# BACALHAU CLI location
: "${BACALHAU_INSTALL_DIR:="/usr/local/bin"}"

# sudo is required to copy binary to BACALHAU_INSTALL_DIR for linux
: "${USE_SUDO:="false"}"

# Option to download pre-releases
: "${PRE_RELEASE:="false"}"

# Http request CLI
BACALHAU_HTTP_REQUEST_CLI=curl

# GitHub Organization and repo name to download release
GITHUB_ORG=bacalhau-project
GITHUB_REPO=bacalhau

# BACALHAU CLI filename
BACALHAU_CLI_FILENAME=bacalhau

BACALHAU_CLI_FILE="${BACALHAU_INSTALL_DIR}/${BACALHAU_CLI_FILENAME}"

BACALHAU_INSTALLATION_ID="BACA14A0-1234-5678-90AB-CDEF12345678"

# shellcheck disable=1054,1083,1073,1056,1072,1009
BACALHAU_ENDPOINT="https://i.bacalhau.org" 

# shellcheck disable=1054,1083,1073,1056,1072,1009
BACALHAU_INSTALL_SCRIPT_HASH="6ec4ced8e921fd27a735293a7d35a21440e84bb48669de0437b3991e6022bf44"

BACALHAU_PUBLIC_KEY=$(cat <<-END
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA7bXxrECk3tQfKox7MDaN
OAQ+NATnILQ9XFfYHs+4Q04lK1tHpvUEwm9OwidMJKlr+M1f/9rzLYV6RDrv0FuA
xaxGS6xrYwmLiXhDj4KwU3v5e6lHhzupsj+7LNSZ9g+ppCXcw73l5wtNmFojKQDH
vpKDzB2KKqRq7/TRenNwvMD02zuDcjGdgXSeSiyIZ6jCn9Y6pX7nPF4rOxpFSL/w
oSb5q5tVY3ZqyrNx/Bk9mBoX3a8xDqFtthuC6SjIF1t5arLih2yEpq8hOdGyyX1l
uQCYlYuIwsYZL+fj2fFzhqpmrHBB97Npw1bTjnzQ8HQIsxkrMEg9ePFfcRfWw7w6
nWBLD4JOTFOoi9SPB0BdyqvE8B+6FTlT8XbK7/VtheR4yFVHvrnVkGzIm6AnwINc
9yFlS5FbxHh0vzL5G4jTYVZrZ7YaQ/zxgZ/SHE9fcSZv4l+W2vlo1EivtOgy1Ee6
OfDFMvdHyg04qjOGxUzYDxZ4/AL+ywSm1HDXP93Oi8icKXy5OANogW4XZ5hll54g
4EBqSON/HH4eIvyWTfFG+U6DBtD0Qn4gZO9y1KUNbhDQ0Z6LOC/mKgWhPSKRdFJk
L9lmeqYFIvAnBx5rmyE7Hlzqk4pSRfggra0D2ydTV79tUQGlX5wpkwch/s4nRmZb
rZd9rvTsifOjf2jxGGu5N6ECAwEAAQ==
-----END PUBLIC KEY-----
END
)

# Current time in nanoseconds
START_TIME=$(date +%s)

# --- Utility Functions ---
import_command() {
    command -v "$1" > /dev/null 2>&1
}

pushEvent() {
    event_name=$1
    event_data=${2:-""}
    sent_at=$(date +"%Y-%m-%d %T")
    elapsed_time_in_seconds=$(($(date +%s) - $START_TIME))

    # If event_data is not empty, append "||" to it
    if [ -z "$event_data" ]; then
        event_data="${event_data}||"
    else
        event_data="${event_data}"
    fi

    event_name="client.install_script.${event_name}"

    # Add installation ID and install script hash to event data
    event_data="${event_data}||bacalhau_testing=$BACALHAU_TESTING"
    event_data="${event_data}||install_script_hash=$BACALHAU_INSTALL_SCRIPT_HASH"
    event_data="${event_data}||metrics=elapsed_time_in_seconds:${elapsed_time_in_seconds}"

    if import_command "curl"; then
        curl -s -X POST -d "{ \"uuid\": \"${BACALHAU_INSTALLATION_ID}\", \"event_name\": \"${event_name}\", \"event_data\": \"${event_data}\", \"sent_at\": \"${sent_at}\" }" -m 5 "$BACALHAU_ENDPOINT" >/dev/null &
    fi
}

command_exists() {
    import_command "$1"
}


addInstallationID() {
  # Use the value of $BACALHAU_DIR if it exists, otherwise default to ~/.bacalhau
  local BACALHAU_DIR="${BACALHAU_DIR:-$HOME/.bacalhau}"
  local CONFIG_FILE="$BACALHAU_DIR/config.yaml"

  # Create the directory if it doesn't exist
  mkdir -p "$BACALHAU_DIR" 
 
    # If the flock command exists, use it
    if command_exists "flock"; then
        # Use a lock file to prevent race conditions
        local LOCK_FILE="$BACALHAU_DIR/config.lock"
        exec 9>"$LOCK_FILE"
        flock -x 9 || { echo "Failed to acquire lock"; pushEvent "failed_to_acquire_lock"; return 1; } # Exit function, not script
    fi

  if [ ! -f "$CONFIG_FILE" ]; then
    # No config file exists; create one with the installation ID.
    echo "User:" > "$CONFIG_FILE"
    echo "  InstallationID: $BACALHAU_INSTALLATION_ID" >> "$CONFIG_FILE"
  else
    # Normalize the config file to remove extra spacing and empty lines
    awk 'NF > 0' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

    # Read the existing installation ID (if present) into a variable
    existing_installation_id=$(awk '/^ *InstallationID:/{print $2}' "$CONFIG_FILE")

    if [ -z "$existing_installation_id" ]; then
      # If InstallationID doesn't exist, add it under the User section
      awk -v installation_id="$BACALHAU_INSTALLATION_ID" '/^ *User:/{print; print "  InstallationID:", installation_id; next} 1' "$CONFIG_FILE" > "$BACALHAU_DIR/config.tmp" && mv "$BACALHAU_DIR/config.tmp" "$CONFIG_FILE"
    else
      # Installation ID exists; replace it, preserving the rest of the config
      sed -i "s/ *InstallationID: .*/  InstallationID: $BACALHAU_INSTALLATION_ID/" "$CONFIG_FILE" 
    fi
  fi

  # Release the lock
  if command_exists "flock"; then
    flock -u 9
    rm "$LOCK_FILE"
  fi
  return 0 # Success!
}


getSystemInfo() {
    ARCH=$(uname -m)
    case $ARCH in
        armv7*) ARCH="arm" ;;
        aarch64) ARCH="arm64" ;;
        x86_64) ARCH="amd64" ;;
    esac

    OS=$(eval "echo $(uname)|tr '[:upper:]' '[:lower:]'")

    # Most linux distro needs root permission to copy the file to /usr/local/bin
    if [ "$OS" == "linux" ] && [ "$BACALHAU_INSTALL_DIR" == "/usr/local/bin" ]; then
        USE_SUDO="true"
    # Darwin needs permission to copy the file to /usr/local/bin
    elif [ "$OS" == "darwin" ] && [ "$BACALHAU_INSTALL_DIR" == "/usr/local/bin" ]; then
        USE_SUDO="true"
    fi

    # If lsb_release command is available, use it to detect distro. Otherwise - have variable be NOLSB
    if [ -x "$(command -v lsb_release)" ]; then
        DISTRO=$(lsb_release -si)
    else
        DISTRO="NOLSB"
    fi
    
    pushEvent "verify_system_info" "operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
}

verifySupported() {
    local supported=(linux-amd64 linux-arm64 darwin-amd64 darwin-arm64)
    local current_osarch="${OS}-${ARCH}"

    for osarch in "${supported[@]}"; do
        if [ "$osarch" == "$current_osarch" ]; then
            echo "Your system is ${OS}_${ARCH}. Your platform is $DISTRO."
            return
        fi
    done

    echo "No prebuilt binary for ${current_osarch} and platform ${DISTRO}."
    pushEvent "failed_os_arch" "operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
    exit 1
}

runAsRoot() {
    local CMD="$*"

    if [ $EUID -ne 0 ] && [ "$USE_SUDO" = "true" ]; then
        CMD="sudo $CMD"
    fi

    $CMD
}

checkHttpRequestCLI() {
    if command_exists "curl" > /dev/null; then
        BACALHAU_HTTP_REQUEST_CLI=curl
    elif command_exists "wget" > /dev/null; then
        BACALHAU_HTTP_REQUEST_CLI=wget
    else
        echo "Either curl or wget is required"
        exit 1
    fi
}

checkExistingBacalhau() {
    if [ -f "$BACALHAU_CLI_FILE" ]; then
        client_version=$($BACALHAU_CLI_FILE version --client --no-style --output csv --hide-header | cut -d, -f1)
        echo -e "\nBACALHAU CLI is detected: $client_version"
        echo -e "Reinstalling BACALHAU CLI - ${BACALHAU_CLI_FILE}..."
        pushEvent "bacalhau_detected" "client_version=$client_version"
    else
        echo -e "No BACALHAU detected. Installing fresh BACALHAU CLI..."
        pushEvent "no_bacalhau_detected"
    fi
}

getLatestRelease() {
    # /latest ignores pre-releases, see https://docs.github.com/en/rest/releases/releases#get-the-latest-release
    local tag_regex='v?[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)*'
    if [ "$PRE_RELEASE" == "true" ]; then
        echo "Installing most recent pre-release version..."
        local bacalhauReleaseUrl="https://api.github.com/repos/${GITHUB_ORG}/${GITHUB_REPO}/releases?per_page=1"
    else
        local bacalhauReleaseUrl="https://api.github.com/repos/${GITHUB_ORG}/${GITHUB_REPO}/releases/latest"
    fi

    local latest_release=""

    if [ "$BACALHAU_HTTP_REQUEST_CLI" == "curl" ]; then
                latest_release=$(curl -s $bacalhauReleaseUrl  | grep \"tag_name\" | grep -E -i "\"$tag_regex\"" | awk 'NR==1{print $2}' | sed -n 's/\"\(.*\)\",/\1/p')
    else
        latest_release=$(wget -q --header="Accept: application/json" -O - "$bacalhauReleaseUrl" | grep \"tag_name\" | grep -E -i "^$tag_regex$" | awk 'NR==1{print $2}' |  sed -n 's/\"\(.*\)\",/\1/p')
    fi

    ret_val=$latest_release
}
# --- create temporary directory and cleanup when done ---
setup_tmp() {
    BACALHAU_TMP_ROOT=$(mktemp -d 2>/dev/null || mktemp -d -t 'bacalhau-install.XXXXXXXXXX')
    cleanup() {
        code=$?
        set +e
        trap - EXIT
        rm -rf "${BACALHAU_TMP_ROOT}"
        exit $code
    }
    trap cleanup INT EXIT
}

downloadFile() {
    LATEST_RELEASE_TAG=$1

    BACALHAU_CLI_ARTIFACT="${BACALHAU_CLI_FILENAME}_${LATEST_RELEASE_TAG}_${OS}_${ARCH}.tar.gz"
    BACALHAU_SIG_ARTIFACT="${BACALHAU_CLI_ARTIFACT}.signature.sha256"

    DOWNLOAD_BASE="https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/releases/download"

    CLI_DOWNLOAD_URL="${DOWNLOAD_BASE}/${LATEST_RELEASE_TAG}/${BACALHAU_CLI_ARTIFACT}"
    SIG_DOWNLOAD_URL="${DOWNLOAD_BASE}/${LATEST_RELEASE_TAG}/${BACALHAU_SIG_ARTIFACT}"

    CLI_TMP_FILE="$BACALHAU_TMP_ROOT/$BACALHAU_CLI_ARTIFACT"
    SIG_TMP_FILE="$BACALHAU_TMP_ROOT/$BACALHAU_SIG_ARTIFACT"

    echo "Downloading $CLI_DOWNLOAD_URL ..."
    if [ "$BACALHAU_HTTP_REQUEST_CLI" == "curl" ]; then
        curl -SsLN "$CLI_DOWNLOAD_URL" -o "$CLI_TMP_FILE"
    else
        wget -q -O "$CLI_TMP_FILE" "$CLI_DOWNLOAD_URL"
    fi

    if [ ! -f "$CLI_TMP_FILE" ]; then
        echo "failed to download $CLI_DOWNLOAD_URL ..."
        exit 1
    fi

    pushEvent "downloaded_file"



    echo "Downloading sig file $SIG_DOWNLOAD_URL ..."
    if [ "$BACALHAU_HTTP_REQUEST_CLI" == "curl" ]; then
        curl -SsLN "$SIG_DOWNLOAD_URL" -o "$SIG_TMP_FILE"
    else
        wget -q -O "$SIG_TMP_FILE" "$SIG_DOWNLOAD_URL"
    fi

    if [ ! -f "$SIG_TMP_FILE" ]; then
        echo "failed to download $SIG_DOWNLOAD_URL ..."
        exit 1
    fi

    pushEvent "downloaded_sig_file"
}

verifyTarBall() {
    if ! command -v openssl &> /dev/null
    then
        echo "WARNING: openssl could not be found. We are NOT verifying this tarball is correct!"
        pushEvent "no_open_ssl_found"
        return
    fi

    echo "$BACALHAU_PUBLIC_KEY" > "$BACALHAU_TMP_ROOT/BACALHAU_public_file.pem"
    openssl base64 -d -in "$SIG_TMP_FILE" -out "$SIG_TMP_FILE".decoded
    if openssl dgst -sha256 -verify "$BACALHAU_TMP_ROOT/BACALHAU_public_file.pem" -signature "$SIG_TMP_FILE".decoded "$CLI_TMP_FILE" ; then
        # Above command echos "Verified Ok"
        pushEvent "verified_tarball"
        return
    else
        echo "Failed to verify signature of tarball."
        pushEvent "failed_to_verify_tarball"
        exit 1
    fi
}

expandTarball() {
    echo "Extracting tarball ..."
    # echo "Extract tar file - $CLI_TMP_FILE to $BACALHAU_TMP_ROOT"
    tar xzf "$CLI_TMP_FILE" -C "$BACALHAU_TMP_ROOT"
}

verifyBin() {
    # openssl base64 -d -in $BACALHAU_TMP_ROOT/bacalhau.signature.sha256 -out $BACALHAU_TMP_ROOT/bacalhau.signature.sha256.decoded
    # if openssl dgst -sha256 -verify "$BACALHAU_TMP_ROOT/BACALHAU_public_file.pem" -signature $BACALHAU_TMP_ROOT/bacalhau.signature.sha256.decoded $BACALHAU_TMP_ROOT/bacalhau; then
    #     return
    # else
    #     echo "Failed to verify signature of bacalhau binary."
    #     exit 1
    # fi
    echo "NOT verifying Bin"
}


installFile() {
    local tmp_root_bacalhau_cli="$BACALHAU_TMP_ROOT/$BACALHAU_CLI_FILENAME"

    if [ ! -f "$tmp_root_bacalhau_cli" ]; then
        echo "Failed to unpack BACALHAU CLI executable."
        exit 1
    fi

    chmod o+x "$tmp_root_bacalhau_cli"
    if [ -f "$BACALHAU_CLI_FILE" ]; then
        runAsRoot rm -f "$BACALHAU_CLI_FILE"
    fi
    if [ ! -d "$BACALHAU_INSTALL_DIR" ]; then
        runAsRoot mkdir -p "$BACALHAU_INSTALL_DIR"
    fi
    runAsRoot cp "$tmp_root_bacalhau_cli" "$BACALHAU_CLI_FILE"

    if [ -f "$BACALHAU_CLI_FILE" ]; then
        echo "$BACALHAU_CLI_FILENAME installed into $BACALHAU_INSTALL_DIR successfully."
        $BACALHAU_CLI_FILE version
    else
        echo "Failed to install $BACALHAU_CLI_FILENAME"
        exit 1
    fi

    if [ ! "$(which bacalhau)" = "$BACALHAU_CLI_FILE" ]; then
        echo "WARNING: $BACALHAU_CLI_FILE not on PATH: $PATH" 1>&2 
    fi

    pushEvent "finished_installation"
}

fail_trap() {
    result=$?
    if [ "$result" != "0" ]; then
        echo "Failed to install BACALHAU CLI"
        echo "For support, go to https://github.com/${GITHUB_ORG}/${GITHUB_REPO}"
    fi
    pushEvent "in_trap_failed_for_any_reason" "result=$result"
    cleanup
    exit "$result"
}

cleanup() {
    if [[ -d "${BACALHAU_TMP_ROOT:-}" ]]; then
        rm -rf "$BACALHAU_TMP_ROOT"
    fi
}

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
trap "fail_trap" EXIT

cat << EOF


            ......     :^^^^:
             ^!!!!^    .?PPP5!
              .~!!!~:    ~555PJ:
               ^!!!!^     .::::.:~~~~^.
             :~!!!~.             .~!!!~:        ____          _____          _      _    _         _    _
^7!!!~      ^!!!!^                 ^!!!!^      |  _ \   /\   / ____|   /\   | |    | |  | |   /\  | |  | |
.7PPPP?.  .~!!!~:             .^~~. .~!!!~:    | |_) | /  \ | |       /  \  | |    | |__| |  /  \ | |  | |
  :YPPP5^^!!!!^       ~7777~ .YPPP5.  ^!!!!^   |  _ < / /\ \| |      / /\ \ | |    |  __  | / /\ \| |  | |
  !5PPPJ::!!!!~.    .?PPPP7.  7555?. .~!!!!:   | |_) / ____ \ |____ / ____ \| |____| |  | |/ ____ \ |__| |
:JPPP5!   .^!!!!:  .?YJJJ^     ...  :!!!!~.    |____/_/    \_\_____/_/    \_\______|_|  |_/_/    \_\____/
:^^^^:      :!!!!~.               .~!!!!:
             .~!!!!:             :!!!!~.
               :^^^^:           :^^^^:

Distributed Compute over Data

Bacalhau Repository
https://link.cod.dev/bacalhau-repo

Please file an issue if you encounter any problems!
https://link.cod.dev/bacalhau-new-issue

===============================================================================
EOF

getSystemInfo
verifySupported
checkExistingBacalhau
checkHttpRequestCLI

if [ -z "$1" ]; then
    echo "Getting the latest BACALHAU CLI..."
    getLatestRelease
else
    ret_val=v$1
fi

if [ -z "$ret_val" ]; then
    echo 1>&2 "Error getting latest release... Please file a bug here: https://github.com/bacalhau-project/bacalhau/issues/new"
    exit 1
fi

echo "Installing $ret_val BACALHAU CLI..."

setup_tmp
addInstallationID
downloadFile "$ret_val"
verifyTarBall
expandTarball
verifyBin
installFile

cat << EOF

  _______ _    _          _   _ _  __ __     ______  _    _
 |__   __| |  | |   /\   | \ | | |/ / \ \   / / __ \| |  | |
    | |  | |__| |  /  \  |  \| |   /   \ \_/ / |  | | |  | |
    | |  |  __  | / /\ \ |     |  <     \   /| |  | | |  | |
    | |  | |  | |/ ____ \| |\  |   \     | | | |__| | |__| |
    |_|  |_|  |_/_/    \_\_| \_|_|\_\    |_|  \____/ \____/

Thanks for installing Bacalhau! We're hoping to unlock an new world of more efficient computation and data, and would really love to hear from you on how we can improve.

- ⭐️ Give us a star on GitHub (https://link.cod.dev/bacalhau-repo)
- 🧑‍💻 Request a feature! (https://link.cod.dev/bacalhau-new-issue)
- 🐛 File a bug! (https://link.cod.dev/bacalhau-file-bug)
- ❓ Join our Slack! (https://link.cod.dev/bacalhau-slack)
- 📰 Subscribe to our blog! (https://link.cod.dev/bacalhau-blog)
- ✉️  Join our mailing list! (https://link.cod.dev/bacalhau-discuss)

Thanks again!
~ Team Bacalhau

EOF

cleanup