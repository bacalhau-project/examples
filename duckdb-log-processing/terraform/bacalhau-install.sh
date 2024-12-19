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

# BACALHAU version to install (empty for latest)
: "${BACALHAU_VERSION:=""}"

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

BACALHAU_INSTALLATION_ID=""

BACALHAU_METRICS_ENDPOINT="https://i.bacalhau.org"

BACALHAU_INSTALL_SCRIPT_HASH="5aebcbf3842d2cef05393e7e997f84db8bc1fde6"

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

usage() {
    echo "Usage: $0 [VERSION] [options]"
    echo "or:    $0 [options]"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION    Specify Bacalhau version to install (with or without 'v' prefix)"
    echo "  -d, --dir DIRECTORY      Specify installation directory"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "If VERSION is provided as the first argument, it will be used as the version to install."
}

# Check if the first argument is a version (doesn't start with a dash)
if [[ $1 && $1 != -* ]]; then
    BACALHAU_VERSION="$1"
    shift
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -v|--version)
        BACALHAU_VERSION="$2"
        shift # past argument
        shift # past value
        ;;
        -d|--dir)
        BACALHAU_INSTALL_DIR="$2"
        shift # past argument
        shift # past value
        ;;
        -h|--help)
        usage
        exit 0
        ;;
        *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
done

# Update BACALHAU_CLI_FILE with the new install directory
BACALHAU_CLI_FILE="${BACALHAU_INSTALL_DIR}/${BACALHAU_CLI_FILENAME}"

# Current time in nanoseconds
START_TIME=$(date +%s)

# --- Utility Functions ---
import_command() {
    command -v "$1" > /dev/null 2>&1
}

pushEvent() {
    # If BACALHAU_METRICS_ENDPOINT is not set, return
    [ -z "$BACALHAU_METRICS_ENDPOINT" ] && return

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
        curl -s -X POST -d "{ \"uuid\": \"${BACALHAU_INSTALLATION_ID}\", \"event_name\": \"${event_name}\", \"event_data\": \"${event_data}\", \"sent_at\": \"${sent_at}\" }" -m 5 "$BACALHAU_METRICS_ENDPOINT" >/dev/null &
    fi
}

command_exists() {
    import_command "$1"
}


addInstallationID() {
    # Return early if BACALHAU_INSTALLATION_ID is empty or still has the placeholder value
    if [ -z "$BACALHAU_INSTALLATION_ID" ] || [[ "$BACALHAU_INSTALLATION_ID" == *REPLACE_ME* ]]; then
        pushEvent "addInstallationID_id_invalid_or_empty" "id=$BACALHAU_INSTALLATION_ID||operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
        return 0  # Best effort: if the id is invalid, return early
    fi

    # Determine the appropriate config directory based on the OS
    local id_file
    if [[ "$OS" == "mingw"* || "$OS" == "msys"* || "$OS" == "cygwin"* ]]; then
        # Use APPDATA on Windows
        id_file="$APPDATA/bacalhau/installation_id"
    else
        # Use XDG standard or default to ~/.config for Linux and Darwin
        local config_dir="${XDG_CONFIG_HOME:-$HOME/.config}"
        id_file="$config_dir/bacalhau/installation_id"
    fi

    # Create the directory if it doesn't exist
    local id_dir
    id_dir=$(dirname "$id_file")
    if ! mkdir -p "$id_dir"; then
        pushEvent "addInstallationID_failed_to_create_id_directory" "directory=$id_dir||operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
        return 0  # Best effort: if mkdir fails, return early
    fi

    # Write the installation ID to the file
    if ! echo "$BACALHAU_INSTALLATION_ID" > "$id_file"; then
        pushEvent "addInstallationID_failed_to_write_installation_id" "file=$id_file||operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
        return 0  # Best effort: if write fails, return early
    fi

    # Set appropriate permissions (readable and writable by user only)
    if ! chmod 600 "$id_file" 2>/dev/null; then
        pushEvent "addInstallationID_failed_to_set_permissions" "file=$id_file||operating_system=$OS||architecture=$ARCH||platform=$DISTRO"
        return 0  # Best effort: if chmod fails, return early
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

createInstallDir() {
    if [ "$USE_SUDO" != "true" ] && [ ! -d "$BACALHAU_INSTALL_DIR" ]; then
        echo "Custom installation directory $BACALHAU_INSTALL_DIR does not exist. Creating it now..."
        mkdir -p "$BACALHAU_INSTALL_DIR"

        if [ $? -eq 0 ]; then
            echo "Successfully created directory $BACALHAU_INSTALL_DIR"
        else
            echo "Failed to create directory $BACALHAU_INSTALL_DIR"
            exit 1
        fi
    fi
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

getReleaseVersion() {
    local bacalhauLatestReleaseVersionUrl
    local max_retries=10
    local retry_delay=3
    local retry_timeout_seconds=60

    if [ -n "$BACALHAU_VERSION" ]; then
        case "$BACALHAU_VERSION" in
            latest)
                PRE_RELEASE=false
                ;;
            pre-release | pre | pre_release)
                PRE_RELEASE=true
                ;;
            *)
                if [[ $BACALHAU_VERSION != v* ]]; then
                    BACALHAU_VERSION="v${BACALHAU_VERSION}"
                fi
                echo "Installing specified version: $BACALHAU_VERSION"
                # check if the signature of a well known arch (linux amd64) , if it is there, that means we have the release version
                # we do not want to fetch the whole release now since it can be huge
                local versionUrl="https://get.bacalhau.org/releases/bacalhau_${BACALHAU_VERSION}_linux_amd64.tar.gz.signature.sha256"
                local versionExists
                if [ "$BACALHAU_HTTP_REQUEST_CLI" == "curl" ]; then
                    versionExists=$(curl -o /dev/null -s -w "%{http_code}" $versionUrl)
                else
                    versionExists=$(wget --server-response -q -O /dev/null $versionUrl 2>&1 | awk '/^  HTTP/{print $2}' | tail -n 1)
                fi
                if [ "$versionExists" != "200" ]; then
                    echo "Error: Version $BACALHAU_VERSION does not exist."
                    echo "Please check available versions at https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/releases"
                    exit 1
                fi
                ret_val="$BACALHAU_VERSION"
                return
                ;;
        esac
    fi

    if [ "$PRE_RELEASE" == "true" ]; then
        echo "Installing most recent pre-release version..."
        bacalhauLatestReleaseVersionUrl="https://get.bacalhau.org/releases/latest?pre-release=true"
    else
        bacalhauLatestReleaseVersionUrl="https://get.bacalhau.org/releases/latest"
    fi

    local latest_release=""
    local http_code

    if [ "$BACALHAU_HTTP_REQUEST_CLI" == "curl" ]; then
        # Create a temporary file for the response, create them in BACALHAU_TMP_ROOT
        local tmp_response
        tmp_response=$(mktemp -p "$BACALHAU_TMP_ROOT" release_latest.XXXXXXXXXX)

        # Get both the HTTP code and body
        http_code=$(curl \
            --retry $max_retries \
            --retry-delay $retry_delay \
            -s -w "%{http_code}" \
            -o "$tmp_response" \
            "$bacalhauLatestReleaseVersionUrl")

        if [ "$http_code" != "200" ]; then
            echo "Error: Failed to fetch latest release. HTTP status code: $http_code"
            pushEvent "failed_to_fetch_latest_release" "http_code=$http_code"
            exit 1
        fi

        # Read the response body
        latest_release=$(cat "$tmp_response")
    else
        # For wget, use separate files for headers and body, create them in BACALHAU_TMP_ROOT
        local tmp_headers
        local tmp_body
        tmp_headers=$(mktemp -p "$BACALHAU_TMP_ROOT" latest_release_headers.XXXXXXXXXX)
        tmp_body=$(mktemp -p "$BACALHAU_TMP_ROOT" latest_release_body.XXXXXXXXXX)

        # Get the response, saving headers to one file and body to another
        wget \
            --tries=$max_retries \
            --wait=$retry_delay \
            --retry-connrefused \
            --timeout=$retry_timeout_seconds \
            --server-response \
            -q -O "$tmp_body" \
            "$bacalhauLatestReleaseVersionUrl" 2>"$tmp_headers"

        # Extract HTTP status code from headers
        http_code=$(awk '/^  HTTP/{print $2}' "$tmp_headers" | tail -n 1)

        if [ "$http_code" != "200" ]; then
            echo "Error: Failed to fetch latest release. HTTP status code: $http_code"
            pushEvent "failed_to_fetch_latest_release" "http_code=$http_code"
            exit 1
        fi

        # Read the response body
        latest_release=$(cat "$tmp_body")
    fi

    # Verify we got a non-empty response
    if [ -z "$latest_release" ]; then
        echo "Error: Received empty response when fetching latest release version"
        pushEvent "empty_latest_release_response" "http_code=$http_code"
        exit 1
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

    DOWNLOAD_BASE="https://get.bacalhau.org/releases"

    CLI_DOWNLOAD_URL="${DOWNLOAD_BASE}/${BACALHAU_CLI_ARTIFACT}"
    SIG_DOWNLOAD_URL="${DOWNLOAD_BASE}/${BACALHAU_SIG_ARTIFACT}"

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

expandTarBall() {
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
        $BACALHAU_CLI_FILE version --client --no-style
    else z
        echo "Failed to install $BACALHAU_CLI_FILENAME"
        exit 1
    fi

    installed_path=$(which bacalhau 2>/dev/null)
    if [ -z "$installed_path" ]; then
        echo "WARNING: $BACALHAU_CLI_FILE is not on your PATH: $PATH" 1>&2
    elif [ "$installed_path" != "$BACALHAU_CLI_FILE" ]; then
        echo "WARNING: The Bacalhau CLI found on your PATH ($installed_path) is different from the one we just installed ($BACALHAU_CLI_FILE)." 1>&2
        echo "You may want to update your PATH or remove old installations." 1>&2
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

createInstallDir
getReleaseVersion

if [ -z "$ret_val" ]; then
    echo 1>&2 "Error getting latest release... Please file a bug here: https://github.com/bacalhau-project/bacalhau/issues/new"
    exit 1
fi

echo "Installing $ret_val BACALHAU CLI in $BACALHAU_INSTALL_DIR..."

setup_tmp
addInstallationID
downloadFile "$ret_val"
verifyTarBall
expandTarBall
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