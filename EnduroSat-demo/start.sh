#!/bin/bash
# Script to warm up the Docker registry cache + prepare edge environment
set -e
echo "Starting registry mirroring and edge node preparation..."
docker compose up -d registry-proxy

# Define registry address
REGISTRY_ADDRESS="localhost:5000"

# Check if registry is accessible
echo "Checking registry connectivity..."
curl -s "http://${REGISTRY_ADDRESS}/v2/" > /dev/null
if [ $? -ne 0 ]; then
    echo "Error: Cannot connect to registry at ${REGISTRY_ADDRESS}"
    echo "Make sure the registry is running and accessible"
    exit 1
fi

#############################
# Step 1: Create local folders for edge nodes
#############################
echo "Creating local folders for node1-5..."
for i in {1..5}; do
    mkdir -p "node${i}-data/input"
    mkdir -p "node${i}-data/output"
done
echo "✅ Edge node folders created"

#############################
# Step 2: Download and prepare model files
#############################
echo "Downloading model files..."
mkdir -p app
mkdir -p app/models


MODELS=(
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x-obb.pt"
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11l-obb.pt"
    "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8x-obb.pt"
    "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8l-obb.pt"
)

for MODEL_URL in "${MODELS[@]}"; do
    FILENAME=$(basename "$MODEL_URL")
    DEST_PATH="app/models/$FILENAME"
    if [ ! -f "$DEST_PATH" ]; then
        echo "Downloading $FILENAME..."
        curl -L -o "$DEST_PATH" "$MODEL_URL"
        echo "✅ Downloaded $FILENAME to $DEST_PATH"
    else
        echo "Model file $FILENAME already exists, skipping download."
    fi
done

echo "✅ All base models downloaded to app/models"


MODEL_TMP="app/models/yolo11x-obb.pt"
if [ ! -f "$MODEL_TMP" ]; then
    echo "❌ ERROR: Base model $MODEL_TMP not found. Cannot create node models."
    exit 1
fi

echo "Creating model copies for each node..."
for i in {1..5}; do
    cp "$MODEL_TMP" "app/model-node${i}.pt"
done
echo "✅ Model copies created at app/model-nodeX.pt"

#############################
# Step 3: Mirror container images to local registry
#############################
IMAGES=(
    "ghcr.io/bacalhau-project/examples/enduro-sat-torch:10052025"
)

echo "Starting image mirroring..."
for IMAGE in "${IMAGES[@]}"; do
    echo "Processing image: ${IMAGE}"

    if [[ "$IMAGE" == *"/"* && "$IMAGE" != "/"* ]]; then
        REGISTRY_PART=$(echo "$IMAGE" | cut -d'/' -f1)
        if [[ "$REGISTRY_PART" == *"."* || "$REGISTRY_PART" == *":"* ]]; then
            IMAGE_NAME="${IMAGE#*/}"
        else
            IMAGE_NAME="$IMAGE"
        fi
    else
        IMAGE_NAME="library/$IMAGE"
    fi

    echo "Pulling ${IMAGE}..."
    docker pull ${IMAGE}

    echo "Tagging as ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
    docker tag ${IMAGE} ${REGISTRY_ADDRESS}/${IMAGE_NAME}

    echo "Pushing to local registry..."
    docker push ${REGISTRY_ADDRESS}/${IMAGE_NAME}

    echo "Successfully cached ${IMAGE}"
    echo "-----------------------------"
done

#############################
# Step 4: Test pulling from local registry
#############################
echo "Testing pull from local registry..."
for IMAGE in "${IMAGES[@]}"; do
    if [[ "$IMAGE" == *"/"* && "$IMAGE" != "/"* ]]; then
        REGISTRY_PART=$(echo "$IMAGE" | cut -d'/' -f1)
        if [[ "$REGISTRY_PART" == *"."* || "$REGISTRY_PART" == *":"* ]]; then
            IMAGE_NAME="${IMAGE#*/}"
        else
            IMAGE_NAME="$IMAGE"
        fi
    else
        IMAGE_NAME="library/$IMAGE"
    fi

    echo "Removing local image ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
    docker rmi ${REGISTRY_ADDRESS}/${IMAGE_NAME} || true

    echo "Pulling from local registry: ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
    docker pull ${REGISTRY_ADDRESS}/${IMAGE_NAME}

    if [ $? -eq 0 ]; then
        echo "✅ Successfully pulled ${REGISTRY_ADDRESS}/${IMAGE_NAME} from local registry"
    else
        echo "❌ Failed to pull ${REGISTRY_ADDRESS}/${IMAGE_NAME} from local registry"
    fi
    echo "-----------------------------"
done
chmod +x scripts/start.sh
chmod +x scripts/disable-network.sh
chmod +x scripts/disable-network.sh
echo "🎉 All preparation complete! Edge folders and models ready. Images mirrored to local registry."

