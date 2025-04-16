
# 🐳 FerretDB Demo Docker Image Builder

This folder contains scripts and Dockerfiles to **build and push Docker images** used in a [FerretDB](https://github.com/FerretDB/FerretDB) demo setup. These images are pulled from their original registries, modified if needed, then **rebuilt, tagged**, and **pushed** to a Docker registry.

## 📦 Contents

- **`enable-qemu-multiarch.sh`** – Enables multi-architecture builds via QEMU.
- **`setup-buildx.sh`** – Sets up Docker Buildx for advanced builds.
- **`ferretdb/`**, **`documentdb/`**, **`minio/`** – Contain `Dockerfile` and helper scripts to build each service.

---

## 🚀 Prerequisites

Make sure you have the following installed:

- Docker (v20.10+)
- Git
- `make` (optional, used in some scripts)
- Bash shell (for running `.sh` scripts)

You can verify with:

```bash
docker --version
git --version
make --version
```

---

## 🔧 Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd <your-repo-dir>
```

### 2. Enable Multi-Architecture Support (Optional)

This step allows building images for other platforms like `arm64`, `riscv`, etc.

```bash
./enable-qemu-multiarch.sh
```

You should see confirmation messages like:
```
✅ QEMU multiarch enabled.
```

### 3. Setup Docker Buildx

This enables extended build functionality.

```bash
./setup-buildx.sh
```

Example output:
```
✅ Buildx builder 'multiarch-builder' is ready.
🔍 Available platforms: linux/amd64, linux/arm64, ...
```

### 4. Build and Push Each Image

Each component has its own folder and a script. **Each script will build and automatically push the image to your Docker registry.**

#### 🧱 DocumentDB

```bash
cd documentdb
./make_copy_of_documentdb.sh
```

#### 🗃️ FerretDB

```bash
cd ../ferretdb
./make_copy_of_ferretdb.sh
```

#### ☁️ MinIO

```bash
cd ../minio
./make_copy_of_minio.sh
```

> **Note:** Ensure you're logged in to your Docker registry using `docker login` before running the scripts.

---

## 🏁 Optional: Sensor Monitoring Dashboard

If you're also working with the `sensor-monitoring-dashboard`, and a `Makefile` is available:

```bash
make build
make push
```

---

## 🧠 Notes

- Scripts are optimized for Linux/macOS.
- For Windows, use WSL2 or adapt the scripts for PowerShell.
