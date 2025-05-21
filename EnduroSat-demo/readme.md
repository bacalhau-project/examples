## 🚀 Quick Start

### 1️⃣ Prepare Environment

```bash
chmod +x start.sh
./start.sh
```
This script downloads required Docker images, models, and creates necessary folders.

```bash
docker compose up -d
```
Starts the orchestrator, compute nodes, MinIO, and all required services.

```bash
docker exec -it sat-demo-client /bin/bash
```
You are now inside the Bacalhau client container and can run jobs.

Run ship detection job:

```bash
bacalhau job run jobs/ship_detect.yaml
```
Run transfer job:

```bash
bacalhau job run jobs/transfer.yaml
```

👉 On a 20 core / 48 GB RAM machine with 1 Gb network, full processing takes ~5 minutes.
👉 UI logs may be unstable (recommended to ignore and monitor docker inside node.

## Input Data
Place your .jpg or .bmp images inside:

```
nodex-data/input
```

You can use script `copy_samples.sh` which copy images from samples directory to directory from argument

```
chmod +x copy_samples.sh
```
Usage
Copy 3 random images into node3-data/input:

```bash
./copy_samples.sh node3-data 5
```

Copy 8 random images into node1-data/input:

```bash
./copy_samples.sh node1-data 10
```

The script will automatically create the target directory if it doesn’t already exist.
## 📡 Network Endpoints
You can dynamically manage the network behavior by calling the following internal APIs (only when ssh to compute-node):

### Open network (allow transfer)
```
localhost:9123
POST /open-network
"Authorization: Bearer abrakadabra1234!@#"
```

### Close network (block transfer)
```
localhost:9123
POST /close-network
"Authorization: Bearer abrakadabra1234!@#"
```

### Set bandwidth level
```bash
curl -X POST http://localhost:9123/set-bandwidth \
-H "Authorization: Bearer abrakadabra1234!@#" \
-H "Content-Type: application/json" \
-d '{"value": "HIGH"}'
```
Default value: LOW → sends all processed data to MinIO.


## 🎯 Models and Job Example
Trigger a model change job from the Bacalhau client:

```bash
bacalhau job run jobs/model.yaml -V SATELLITE_NAME=nodex -V MODEL_NAME=XYZ
```
Example:

```bash
bacalhau job run jobs/model.yaml -V SATELLITE_NAME=node1 -V MODEL_NAME=yolov8x-obb.pt
```

Available Models

```
yolo11l-obb.pt  
yolo11x-obb.pt  
yolov8l-obb.pt  
yolov8x-obb.pt
```
