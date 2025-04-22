# Cosmos DB with Bacalhau

This project demonstrates how to use Azure Cosmos DB with Bacalhau for data engineering workloads. It includes tools for processing sensor data from SQLite databases and uploading it efficiently to Cosmos DB.

## Project Structure

- `cosmos-uploader/`: Contains the C# application for uploading data to Cosmos DB.
- `config/`: Configuration files for the uploader and simulation (if used).
- `data/`: Directory intended for storing sensor data in SQLite databases.
  - `{city}/{sensor-number}/`: Example structure for SQLite database files.
- `archive/`: Directory intended for archiving processed data.
  - `{city}/`: Example structure for Parquet archive files.
- `sensor_manager/`: Python-based sensor manager/simulator (optional).
- `utility_scripts/`: Miscellaneous helper scripts.

## CosmosDB Uploader

The C# implementation (`cosmos-uploader/`) provides efficient and resilient data ingestion:

- **Optimized Uploads**: Uses the Cosmos DB .NET SDK's bulk execution (`AllowBulkExecution = true`) combined with `CreateItemAsync` and Direct Connection Mode for high throughput and reduced RU cost.
- **SQLite Handling**: Automatically creates necessary indexes (`synced` column) on the source SQLite DB for efficient processing.
- **Resilience**: Leverages SDK built-in retries for transient errors and rate limiting.
- **Development Mode**: Includes a `--development` flag for easy testing (resets SQLite sync status, overwrites item IDs and timestamps).
- **Continuous Mode**: Can run continuously, polling for new data.
- **Data Archiving**: Optional archiving of processed data to Parquet files.
- **Configurable**: Performance and behavior controlled via a YAML configuration file.

See the [Cosmos Uploader README](cosmos-uploader/README.md) for detailed usage instructions.

## Getting Started

### Prerequisites

- Docker and Docker Compose (optional, if using containerization or sensor manager)
- .NET 9.0 SDK (for building/running the uploader directly)
- Azure Cosmos DB account
- Source SQLite database(s) with sensor data

### Configuration

1. Create a `cosmos-config.yaml` file (see `cosmos-uploader/README.md` or `config/` for structure).
2. Populate it with your Azure Cosmos DB `endpoint`, `key`, `database`, `container`, and `partition_key` details.
3. Set performance and logging options as needed.

### Running the Uploader Directly

```bash
cd cosmos-uploader
dotnet restore
dotnet build

# Example: Run once
dotnet run --config path/to/cosmos-config.yaml --sqlite /path/to/your/sensor_data.db

# Example: Run continuously in development mode
dotnet run --config path/to/cosmos-config.yaml --sqlite /path/to/your/sensor_data.db --continuous --development
```

### Using the (Optional) Sensor Manager

If you need to simulate sensor data generation, the Python-based Sensor Manager (`sensor_manager/`) can orchestrate the simulation and the uploader containers.

> **Note**: The Sensor Manager might require separate setup (e.g., `uv`). Refer to its specific documentation.

```bash
# Example: Start simulation and uploaders defined in sensor manager config
./sensor_manager.py start

# Example: Stop the system
./sensor_manager.py stop
```
See the [Python Sensor Manager Documentation](sensor_manager/README.md) for details.

## Querying Cosmos DB

The Python query tool (`cosmos-uploader/query.py`) helps verify data:

```bash
# Requires 'uv' or manual dependency installation for the query tool
cd cosmos-uploader
# Assuming uv is installed and configured for the query tool's env

# Example: Count documents
uv run query.py --config path/to/cosmos-config.yaml --count

# Example: Get latest 5 from a city
uv run query.py --config path/to/cosmos-config.yaml --city Amsterdam --limit 5
```
See [cosmos-query-tool.md](docs/cosmos-query-tool.md) for more.

## Setting Up Azure Cosmos DB

*(This section remains largely the same - ensure variables match your config)*

### Setting Environment Variables (Example)

```bash
export RESOURCE_GROUP="CosmosDB-RG"
export LOCATION="brazilsouth"
export UNIQUE_SUFFIX=$RANDOM
export COSMOS_ACCOUNT_NAME="cosmos-bacalhau-${UNIQUE_SUFFIX}"
export DATABASE_NAME="SensorData" # Match config
export CONTAINER_NAME="SensorReadings" # Match config
export PARTITION_KEY="/city" # Match config
# export THROUGHPUT=400 # Removed: Not applicable for Serverless
```

### Creating Resources via Azure CLI

*(Commands remain the same, except for container creation)*

1.  `az login`
2.  `az group create ...`
3.  `az cosmosdb create ...` (Ensure `--capabilities EnableServerless` is used if creating a new Serverless account)
4.  `az cosmosdb sql database create ...`
5.  `az cosmosdb sql container create ...` (Remove `--throughput` parameter for Serverless)
    ```bash
    # Example for Serverless container:
    az cosmosdb sql container create \
        --account-name $COSMOS_ACCOUNT_NAME \
        --resource-group $RESOURCE_GROUP \
        --database-name $DATABASE_NAME \
        --name $CONTAINER_NAME \
        --partition-key-path $PARTITION_KEY
    ```
6.  Get connection info (`az cosmosdb show ...`, `az cosmosdb keys list ...`)

## Performance Considerations

The C# uploader leverages several Azure Cosmos DB .NET SDK features for optimized throughput:

1.  **Bulk Execution**: Enabled via `AllowBulkExecution = true`, the SDK efficiently batches operations (`CreateItemAsync`) into fewer network requests.
2.  **Direct Connection Mode**: Reduces network latency compared to Gateway mode (ensure required TCP ports are open).
3.  **Optimized Operations**: Using `CreateItemAsync` avoids the read-before-write overhead of upserts when ingesting new data.
4.  **SDK Retries**: Handles transient errors like rate limiting (HTTP 429) automatically based on `CosmosClientOptions`.
5.  **Partitioning**: Relies on a well-distributed partition key (`/city` in the example) for scalable writes.

These features significantly improve ingestion performance compared to single-item operations.

## Troubleshooting

*(Consolidated and updated)*

1.  **Build Issues**: Ensure correct .NET SDK (9.0) is installed. Check Dockerfile paths if containerizing.
2.  **Cosmos DB Connection**: Verify endpoint/key in config. Check container existence and partition key (`/city`). Ensure firewall allows Direct Mode TCP ports (10250-10255) if used.
3.  **Data Processing**: Check SQLite file path and schema (`sensor_readings` table, `synced` column). Monitor uploader logs for errors.
4.  **Performance**: Monitor RU consumption in Azure Portal. Check client CPU/memory usage.

5.  **DNS Resolution Issues Inside Container**:
    *   **Symptom**: The uploader fails to connect to the Cosmos DB endpoint, potentially logging errors related to name resolution or unknown host. This might occur even if the host machine can resolve the address.
    *   **Diagnosis (run inside the container)**:
        1.  Get a shell inside the running container (e.g., `docker exec -it <container_id_or_name> /bin/bash`).
        2.  Install necessary tools (if not present in the base image):
            ```bash
            # Example for Debian/Ubuntu-based images
            apt-get update && apt-get install -y dnsutils iputils-ping telnet traceroute
            ```
        3.  Check which DNS servers the container is configured to use:
            ```bash
            cat /etc/resolv.conf
            ```
            *(Note the `nameserver` IP addresses listed, e.g., `8.8.8.8`)*
        4.  Attempt to resolve the Cosmos DB endpoint using the container's configured DNS:
            ```bash
            nslookup your-cosmos-account.documents.azure.com
            ```
            *(Replace with your actual endpoint. Timeouts or failures here indicate a DNS problem.)*
        5.  Test connectivity to the DNS server itself (use an IP from `resolv.conf`):
            ```bash
            ping -c 3 8.8.8.8
            traceroute -T -p 53 8.8.8.8 # Test UDP port 53 connectivity
            ```
            *(`traceroute` stopping with `* * *` can indicate where the block occurs.)*
    *   **Likely Cause**: Outbound network traffic on UDP port 53 (used for DNS lookups) is being blocked by a firewall rule. This block could be on the host machine's firewall (e.g., `iptables`) or, more commonly, in an external firewall or cloud Network Security Group (NSG) applied to the host.
    *   **Solutions**:
        1.  **(Recommended)** **Adjust External Firewall/NSG**: Modify the outbound rules for the host machine (where Docker is running) to ALLOW UDP traffic on destination port 53, originating from the host's IP address, to the required DNS server IPs (e.g., `8.8.8.8`, `8.8.4.4`) or to `0.0.0.0/0` for general DNS access. Ensure this rule has priority over potential DENY rules.
        2.  **(Workaround)** **Configure Docker Daemon DNS**: If the host machine *can* resolve DNS, configure the Docker daemon to use the host's resolver or a known-good internal DNS server.
            *   Edit `/etc/docker/daemon.json` on the host (create if it doesn't exist):
                ```json
                {
                  "dns": ["<host_nameserver_ip>", "8.8.8.8"]
                }
                ```
                *(Find `<host_nameserver_ip>` via `cat /etc/resolv.conf` on the host. Replace `8.8.8.8` if needed.)*
            *   Restart the Docker daemon: `sudo systemctl restart docker`
            *   Remove and restart your container(s).
        3.  **(Workaround - Less Ideal)** **Use Host Networking**: Run the container with `--network host`. This bypasses Docker's network isolation, using the host's network directly. It often resolves connectivity but has security implications and potential port conflicts.

## License

MIT License - see the LICENSE file for details.