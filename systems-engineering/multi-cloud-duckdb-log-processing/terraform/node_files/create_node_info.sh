#!/bin/bash

# Get instance metadata with proper error handling
get_metadata() {
  local url=$1
  local headers=$2
  curl -s -f $headers "$url" 2>/dev/null || echo ""
}

# Detect cloud provider and set provider-specific details
if get_metadata "http://metadata.google.internal/" "-H 'Metadata-Flavor: Google'" | grep -q .; then
  PROVIDER="GCP"
  REGION=$(get_metadata "http://metadata.google.internal/computeMetadata/v1/instance/zone" "-H 'Metadata-Flavor: Google'" | cut -d'/' -f4)
  ZONE=$(get_metadata "http://metadata.google.internal/computeMetadata/v1/instance/zone" "-H 'Metadata-Flavor: Google'" | cut -d'/' -f4)
  INSTANCE_IP=$(get_metadata "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" "-H 'Metadata-Flavor: Google'")
  STORAGE_LIB="google.cloud.storage"
elif get_metadata "http://169.254.169.254/latest/meta-data/" | grep -q .; then
  PROVIDER="AWS"
  REGION=$(get_metadata "http://169.254.169.254/latest/meta-data/placement/region")
  ZONE=$(get_metadata "http://169.254.169.254/latest/meta-data/placement/availability-zone")
  INSTANCE_IP=$(get_metadata "http://169.254.169.254/latest/meta-data/public-ipv4")
  STORAGE_LIB="boto3"
elif get_metadata "http://169.254.169.254/metadata/instance?api-version=2021-02-01" "-H 'Metadata: true'" | grep -q .; then
  PROVIDER="AZURE"
  REGION=$(get_metadata "http://169.254.169.254/metadata/instance/compute/location?api-version=2021-02-01&format=text" "-H 'Metadata: true'")
  ZONE=$REGION
  INSTANCE_IP=$(get_metadata "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" "-H 'Metadata: true'")
  STORAGE_LIB="azure.storage.blob"
else
  PROVIDER="OCI"
  REGION=$(get_metadata "http://169.254.169.254/opc/v1/instance/region")
  ZONE=$REGION
  INSTANCE_IP=$(get_metadata "http://169.254.169.254/opc/v1/instance/networkInterfaces/0/publicIp")
  STORAGE_LIB="oci.object_storage"
fi

# Generate NODE_INFO file with standardized format
cat > /etc/NODE_INFO << EOF
provider=$PROVIDER
storage_lib=$STORAGE_LIB
STORAGE_BUCKET=${1}-$REGION-${2}
$PROVIDER.region=$REGION
$PROVIDER.zone=$ZONE
$PROVIDER.name=${3}
ip=$INSTANCE_IP
EOF

chmod 0444 /etc/NODE_INFO

# Install required cloud storage libraries
pip3 install $STORAGE_LIB 