#!/usr/bin/env bash
set -e

# shellcheck disable=SC1091
source /app/.venv/bin/activate 

# Quit if any of the required environment variables are missing
required_vars=(PORT HOST WEIGHTSDIR VIDEOSDIR)

# Collect all the missing variables
missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

# If there are missing variables, print an error message and exit
if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "The following environment variables are missing: ${missing_vars[*]}"
    exit 1
fi

python3 /app/wsgi.py --port "$PORT" \
    --host "$HOST" \
    --source_weights_path "$WEIGHTSDIR" \
    --source_all_videos_path "$VIDEOSDIR"

