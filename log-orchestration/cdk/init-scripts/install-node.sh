

# Define start commands using environment variables
orchestrator_start_cmd="/usr/local/bin/bacalhau serve \\
            --node-type requester"

compute_start_cmd="/usr/local/bin/bacalhau serve \\
            --node-type compute \\
            --job-selection-data-locality anywhere \\
            --job-selection-accept-networked \\
            --allow-listed-local-paths '/data/log-orchestration/**:rw' \\
            --peer /ip4/$BACALHAU_ORCHESTRATOR_IP/tcp/1234/http \\
            --labels $BACALHAU_LABELS"

function install-docker() {
  echo "Installing Docker"
  sudo apt-get install -y \
      ca-certificates \
      curl \
      gnupg \
      lsb-release
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
}

function install-aws-cli() {
  sudo apt-get install unzip

  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip awscliv2.zip
  sudo ./aws/install
}

function attach-data-disk() {
  # Define your parameters
  INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
  DEVICE_PATH="/dev/sdf"
  MAX_RETRIES=10

  # Count for retries
  count=0

  # Function to check if volume is already attached
  is_volume_attached() {
    aws ec2 describe-volumes --volume-ids $VOLUME_ID \
      --query 'Volumes[0].Attachments[0].{InstanceId:InstanceId, Device:Device}' \
      --output json
  }

  # Function to detach volume
  detach_volume() {
    aws ec2 detach-volume --volume-id $VOLUME_ID
  }

  # Function to attach volume
  attach_volume() {
    aws ec2 attach-volume --volume-id $VOLUME_ID --instance-id $INSTANCE_ID --device $DEVICE_PATH
  }

  # Check if volume is already attached
  attachment_info=$(is_volume_attached)
  existing_instance=$(echo $attachment_info | jq -r '.InstanceId')
  existing_device=$(echo $attachment_info | jq -r '.Device')

  if [ "$existing_instance" != "null" ]; then
    if [ "$existing_instance" == "$INSTANCE_ID" ] && [ "$existing_device" == "$DEVICE_PATH" ]; then
      echo "Volume is already attached to the desired instance and device. Nothing to do."
      return
    else
      echo "Volume is attached to instance $existing_instance at device $existing_device. Detaching..."
      detach_volume

      # Poll until volume is detached
      while true; do
        sleep 5
        attachment_info=$(is_volume_attached)
        existing_instance=$(echo $attachment_info | jq -r '.InstanceId')

        if [ "$existing_instance" == "null" ]; then
          echo "Volume is detached."
          break
        else
          echo "Waiting for volume to detach..."
          sleep 5
        fi
      done
    fi
  fi

  # Try attaching the volume
  until attach_volume; do
    sleep 10
    count=$(($count + 1))

    # Break if max retries reached
    if [ $count -ge $MAX_RETRIES ]; then
      echo "Max retries reached. Exiting."
      exit 1
    fi

    echo "Retrying to attach volume..."
  done

  echo "Volume successfully attached."
}

function mount-disk() {
  local mount_point=$1
  local devices=("$@")

  echo "Mounting disk at $mount_point"

  local RETRY_COUNT=0
  local MAX_RETRIES=60
  local SLEEP_TIME=1s
  local DEVICE_NAME=""

  while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    for device in "${devices[@]:1}"; do
      if [[ -e $device ]]; then
        DEVICE_NAME=$device
        break 2
      fi
    done

    sleep $SLEEP_TIME
    ((RETRY_COUNT++))
  done

  if [[ -z $DEVICE_NAME ]]; then
    echo "Device not found after $MAX_RETRIES retries."
    exit 1
  fi

  mkdir -p $mount_point
  mount $DEVICE_NAME $mount_point || (sudo mkfs -t ext4 $DEVICE_NAME && sudo mount $DEVICE_NAME $mount_point)
}

function create-directories() {
  # Create directories and files required by bacalhau jobs
  mkdir /data/log-orchestration
  mkdir /data/log-orchestration/logs # This is where the logs will be generated
  mkdir /data/log-orchestration/state # This is where logstash checkpoints will be stored
  chown -R ubuntu:ubuntu /data/log-orchestration
}

function install-bacalhau() {
  echo "Installing Bacalhau from release $BACALHAU_VERSION"
  wget -q "https://github.com/bacalhau-project/bacalhau/releases/download/$BACALHAU_VERSION/bacalhau_${BACALHAU_VERSION}_${TARGET_PLATFORM}.tar.gz"
  tar xfv "bacalhau_${BACALHAU_VERSION}_${TARGET_PLATFORM}.tar.gz"
  sudo mv ./bacalhau /usr/local/bin/bacalhau
}

function init-bacalhau() {
  local exec_start="$1"

  # Define the bacalhau.service file
  cat <<EOL > /etc/systemd/system/bacalhau.service
[Unit]
Description=Bacalhau Daemon
Wants=network-online.target systemd-networkd-wait-online.service

[Service]
Environment="BACALHAU_DIR=/data/bacalhau"
Restart=always
RestartSec=5s
ExecStart=$exec_start

[Install]
WantedBy=multi-user.target
EOL

  sudo systemctl start bacalhau
}

function install-compute() {
  install-common
  install-docker
  init-bacalhau "$compute_start_cmd"
}

function install-orchestrator() {
  install-common
  init-bacalhau "$orchestrator_start_cmd"
}

function install-common() {
  sudo apt-get update -y
  sudo apt-get install jq -y

  install-aws-cli
  attach-data-disk
  mount-disk "/data" "/dev/sdf" "/dev/nvme1n1" # Mount the data disk
  create-directories
  install-bacalhau
}

# Main install logic
if [ -z "$BACALHAU_ORCHESTRATOR_IP" ]; then
  install-orchestrator
else
  install-compute
fi