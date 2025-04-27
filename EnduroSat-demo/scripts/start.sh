#!/bin/sh

set -e

# --- CHECK PRIVILEGED ---
if ! iptables -L >/dev/null 2>&1; then
    echo "ERROR: This container must be run with --privileged flag"
    echo "Example: docker run --privileged <image> serve"
    exit 1
fi

# --- RANDOM DELAY ---
HOSTNAME=$(hostname)
INITIAL_DELAY_MS=$(awk -v seed="$(echo $HOSTNAME | cksum | cut -d' ' -f1)" 'BEGIN{srand(seed);print int(rand()*2000)}')
echo "Adding initial startup delay of ${INITIAL_DELAY_MS} milliseconds..."
sleep "$(awk "BEGIN{print ${INITIAL_DELAY_MS}/1000.0}")"

# --- INSTALL DEPENDENCIES ---
apk add --no-cache s3fs-fuse py3-pip
pip install --break-system-packages flask flask_cors gunicorn

# --- INIT DIRECTORIES & FILES ---
mkdir -p /mnt/bufor /bacalhau_data/ /bacalhau_data/metadata /cache /mnt/s3_low /mnt/s3_high

#cp /scripts/generate.py /bacalhau_data/generate.py
#cp /scripts/metadata.sh /bacalhau_data/metadata.sh
echo "${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}" > /etc/passwd-s3fs
chmod 600 /etc/passwd-s3fs

# --- MOUNT S3FS ---
echo "Mounting s3fs..."
s3fs my-bucket /mnt/bufor -o url=http://storage:9000 -o use_path_request_style -o passwd_file=/etc/passwd-s3fs -o nonempty  -o allow_other -o use_cache=/cache
s3fs low-bandwitch /mnt/s3_low -o url=http://storage:9000 -o use_path_request_style -o passwd_file=/etc/passwd-s3fs -o nonempty  -o allow_other -o use_cache=/cache
s3fs high-bandwitch /mnt/s3_high -o url=http://storage:9000 -o use_path_request_style -o passwd_file=/etc/passwd-s3fs -o nonempty  -o allow_other -o use_cache=/cache
# --- START GUNICORN IN BACKGROUND ---
echo "Starting Flask healthz service..."
gunicorn --chdir /scripts healthz-web-server:app -b 0.0.0.0:9123 -w 8 --log-level critical &

# --- WRITE HEALTHCHECK FILE ---
#echo "ok" > /mnt/data/.healthcheck

# --- START DOCKERD ---
MAX_RETRIES=5
ATTEMPT=1
TIMEOUT=45

start_docker_daemon() {
    killall containerd dockerd >/dev/null 2>&1 || true
    sleep 0.5
    rm -f /var/run/docker.pid /var/run/docker.sock /run/containerd/containerd.sock

    echo "Starting Docker daemon (Attempt $ATTEMPT/$MAX_RETRIES)..."
    dockerd-entrypoint.sh dockerd > /var/log/dockerd.log 2>&1 &
    DOCKERD_PID=$!

    start_time=$(date +%s)
    while [ $(( $(date +%s) - start_time )) -lt $TIMEOUT ]; do
        if docker info >/dev/null 2>&1; then
            echo "Docker daemon is ready"
            return 0
        fi

        if ! kill -0 $DOCKERD_PID 2>/dev/null; then
            echo "Docker daemon process died during attempt $ATTEMPT"
            cat /var/log/dockerd.log
            return 1
        fi

        echo "Waiting for Docker daemon... ($(($(date +%s) - start_time))/${TIMEOUT} seconds)"
        sleep 0.5
    done

    echo "Docker daemon failed to start within timeout"
    return 1
}

while [ $ATTEMPT -le $MAX_RETRIES ]; do
    if start_docker_daemon; then
        break
    fi

    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -le $MAX_RETRIES ]; then
        echo "Retrying Docker daemon startup after 1 second..."
        sleep 1
    fi
done

if [ $ATTEMPT -gt $MAX_RETRIES ]; then
    echo "ERROR: Failed to start Docker daemon after $MAX_RETRIES attempts"
    cat /var/log/dockerd.log
    exit 1
fi

# --- START BACALHAU ---
IP=$(hostname -i | awk '{print $1}')
NAME=$(hostname | awk '{print $1}')
echo "Starting bacalhau with IP=$IP"
exec bacalhau serve -c /etc/bacalhau/config.yaml -c "LABELS=PUBLIC_IP=$IP,SATTELITE_NAME=$NAME"
