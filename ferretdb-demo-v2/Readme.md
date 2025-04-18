# FerretDB Sensor Data Demo

This project demonstrates a simulation of distributed sensors operating within the [Bacalhau](https://github.com/bacalhau-project/bacalhau) network. The sensors periodically send their data to a central [FerretDB](https://github.com/FerretDB/FerretDB) instance for storage and analysis.

The entire stack is orchestrated using Docker Compose and includes a user-friendly frontend for visualizing collected sensor data.

---

## 🧰 Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed.
2. A [Google Maps API Key](https://developers.google.com/maps/documentation/embed/get-api-key?hl=en).

---

## ⚙️ Setup

### 1. Configure the Environment

Create a `.env` file in the root directory with your Google Maps API key:

```dotenv
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
```

### 2. Start the Services

Run the following command:

```bash
docker compose up -d
```

This will download the necessary images (if not already present) and launch all services, including:

- Bacalhau Orchestrator
- PostgreSQL (FerretDB backend)
- FerretDB
- MinIO (S3-compatible object storage)
- 5 Sensor Nodes (as Bacalhau compute nodes)
- Frontend dashboard (http://localhost:3010)
- Bacalhau client

### Port Requirements

Ensure the following TCP ports are free:

- **3010** – Frontend
- **8438** – Bacalhau Web Interface
- **27217** – FerretDB (optional external access)
- **9001** – MinIO Web interface
- **Docker subnet `172.28.0.0/16`** must also be available.

> ⚠️ **Note:** FerretDB/PostgreSQL does not currently offer a Docker image for the ARM64 architecture.

---

## 🚀 Running the Demo

### 1. Access the Frontend & Bacalhau Interface

- Frontend: [http://localhost:3010](http://localhost:3010)
- Bacalhau Web UI: [http://localhost:8438](http://localhost:8438)

### 2. Connect to the Client Container

```bash
docker exec -ti ferret-demo-client bash
```

### 3. Start the Sensor Log Generator

```bash
/1_run_generate_sensor_logs_job.sh
```

This starts a **daemon job** that launches a sensor simulator on every sensor container. It may take time to pull necessary images and initialize.

### 4. Start Data Transfer to FerretDB

```bash
/2_run_sync_sensor_logs_job.sh
```

This launches another **daemon job** that periodically transfers sensor data to FerretDB.

Once running, sensors will start appearing on the frontend map and sensor list.

---

## 🔄 Alternative Data Transfer Mode

To reduce transfer volume, you can switch to an **averaged data sync** (once every 30 seconds):

### 5. Replace Sync Script with Averaged Transfer

```bash
/3_replace_sync_sensor_logs_script.sh
```

This runs an **ops job** on every sensor, replacing the default syncer script with one that averages data before transferring it to FerretDB.

To switch back to full data transfer, modify `3_replace_sync_sensor_logs_script.sh`:

```bash
NEW_SYNC_SCRIPT="scripts/average_syncer.py"
#NEW_SYNC_SCRIPT="scripts/sqlite_syncer.py"
```

Replace `NEW_SYNC_SCRIPT` as needed and rerun the script.

---

## 🧹 Optional: Clear All Sensor Data

To clear all sensor data from FerretDB:

```bash
/4_run_cleanup_whole_mongodb_job.sh
```

This runs a **batch job** scheduled on one sensor node to purge all stored data.

---

## 📊 Frontend Dashboard

- Each sensor appears on a Google Map and blinks when new data arrives.
- Sensors will turn red if anomalies are detected.
- Clicking a sensor (map or list) opens a chart view for detailed analysis.

![Map View](docs/screen_map_list.png)
![Sensor Detail](docs/screen_sensor_chart.png)

---

Sure! Here's an updated version of the `README.md` with a new section about tearing everything down using `docker compose down`. I’ve placed it near the end for logical flow:

---

## 🧹 Cleaning Up the Environment

To stop all services and **remove all containers, networks, and volumes created by Docker Compose**, run:

```bash
docker compose down -v
```

This command will:

- Stop all running containers
- Remove the containers and associated networks
- Remove named and anonymous volumes (e.g., any persistent FerretDB or MinIO data)

> ⚠️ Use with caution – this **will erase all sensor data and database contents**.

This is useful if you want to start from scratch or reclaim disk space after testing the demo.


## 🛠️ Troubleshooting

- Check container logs:

```bash
docker logs -f <container-name>
```

- To view all logs in real-time:

```bash
docker compose up
```

*(Remove the `-d` flag to stay attached and view colored logs.)*

- If the frontend map is blank, ensure `.env` exists and includes your Google Maps API key.


- If docker is complaining about overlapping network that already exists, try to prune networks that are not used anymore:
```bash
docker network prune
```

- If there are docker containers present that have the same names, try to prune them also:
```bash
docker container prune
```

---

## ✏️ Development Notes

You can freely edit:

- Job scripts (`jobs/`)
- Python scripts (`scripts/`)

These changes will reflect immediately in the running containers since relevant folders are mounted as volumes.
