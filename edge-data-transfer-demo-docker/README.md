# 🛰️ Bacalhau Edge Sensor Demo

This project simulates a distributed edge network of sensor nodes powered by [Bacalhau](https://github.com/bacalhau-project/bacalhau). Each sensor node acts as a compute node, and periodically sends sensor data to a central storage layer (MinIO). A frontend application displays this data in real-time on an interactive map.

All components are orchestrated using **Docker Compose**, and support multi-architecture builds (AMD64 and ARM64).

---

## 🧰 Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) installed
2. A machine with available ports listed below

---

## ⚙️ Setup

### 1. Preparation

As all Bacalhau jobs are using local private registry it is crucial to populate it before running them.
After bringing up all services with docker compose, run from the host machine:
```bash
private_registry_mirror_warmup.sh
```
This script will pull all job images from the Internet and push them to local registry.
> Volume for registry is exposed to the host machine, so data will still be there after removing everything with docker compose down.


### 1a. (Optional) Configure the Frontend

If needed, adjust the environment variables in `docker-compose.yml` (e.g., `BACALHAU_API_HOST`).
Default is `orchestrator`

### 2. Sensor Behavior

Each sensor runs a custom script from `/scripts/*.sh;` make sure each file has execute permission set using `chmod +x`.


### 3. Start All Services

```bash
docker compose up -d
```

This will start the following services:

- **MinIO** – S3-compatible object storage
- **Bacalhau Orchestrator** – Central control node
- **5 Sensor Nodes** – Simulated compute nodes running Bacalhau jobs
- **Frontend Dashboard** – Accessible via `http://localhost:3000`
- **Client Container** – Used to launch Bacalhau jobs manually

### 📦 Port Requirements

Ensure the following ports are available:

| Port | Description            |
|------|------------------------|
| 3000 | Frontend Dashboard     |
| 8438 | Bacalhau Web Interface |
| 9001 | MinIO Console          |

---

## 🚀 Using the Demo

### 1. Open the Frontend

Visit [http://localhost:3000](http://localhost:3000) to access the dashboard.

### 2. Access the Client Container

```bash
docker exec -ti edge-demo-client /bin/bash
```

From here, you can manually run jobs, transfer data, or debug sensors.

First what you need is generate random data 
```bash
cd /jobs
```
```bash
bacalhau job run generate.yaml
```
Run the data generation job (this may take 5–15 minutes, depending on your machine):
```bash
bacalhau job run create_metadata.yaml
```
Once the data is generated, run the metadata creation job

---

## 🧹 Cleaning Up the Environment

To stop all services and **remove all containers, networks, and volumes**:

```bash
docker compose down -v
```

This will:

- Stop all running containers
- Remove networks and volumes (MinIO storage will be wiped)
- Reset the demo environment completely

---

## 🛠️ Troubleshooting

- Check logs of a specific container:

```bash
docker logs -f <container-name>
```

- Restart everything with live logs:

```bash
docker compose up
```

- Remove unused Docker networks:

```bash
docker network prune
```

- Remove stopped containers:

```bash
docker container prune
```

- If the frontend fails to start on ARM devices, ensure the container is built for `linux/arm64`.

---

## ✏️ Development Notes

- Scripts in `./scripts` and jobs in `./jobs` are mounted into each sensor container.
- You can edit them live and restart containers to test changes.
- The `start.sh` script must be marked executable (`chmod +x`).
- You must run on `LOCALHOST`

---


