# Cosmos Uploader

A .NET 9.0 application for efficiently uploading sensor data from SQLite databases to Azure Cosmos DB.
This tool leverages several optimizations for high throughput and resilience.

## Key Features

- **Bulk Upload**: Utilizes the Cosmos DB SDK's bulk execution (`AllowBulkExecution = true`) for optimal throughput.
- **Direct Connection Mode**: Connects using `ConnectionMode.Direct` for lower latency (requires outbound TCP ports 10250-10255 to be open).
- **Optimized Operations**: Uses `CreateItemAsync` for inserts, assuming sensor data is typically new, reducing RU cost compared to upserts.
- **SQLite Optimization**: Automatically creates an index on the `synced` column in the source SQLite database to speed up post-upload updates.
- **Development Mode**: Includes a `--development` flag to reset SQLite sync status and generate new IDs/timestamps, facilitating testing.
- **Batch Processing**: Reads data from SQLite in batches (though Cosmos bulk handles the upload batching).
- **Data Processing Pipeline (Optional)**: Allows for optional data processing stages before upload:
    - Schematization: Validate/transform raw data.
    - Sanitization: Mask/strip sensitive data.
    - Aggregation: Perform basic aggregation on data.
- **Data Archiving**: Optional archiving of processed data to Parquet files.
- **Continuous Mode**: Can run continuously, polling for new data.
- **Configurable**: Settings managed via a YAML configuration file.

## Prerequisites

- [.NET 9.0 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
- Azure Cosmos DB account with appropriate access credentials
- SQLite databases containing sensor data

## Building the Application

1. Navigate to the `cosmos-uploader` directory:
   ```bash
   cd cosmos-uploader
   ```

2. Restore dependencies and build the application:
   ```bash
   dotnet restore
   dotnet build
   ```

## Configuration

The application uses a YAML configuration file (e.g., `cosmos-config.yaml`) passed via the `--config` argument. See the main project `config/` directory for examples.

```yaml
# Example cosmos-config.yaml structure
cosmos:
  endpoint: "https://your-cosmos-account.documents.azure.com:443/"
  key: "your-cosmos-key"
  database: "SensorData"
  container: "SensorReadings"
  partition_key: "/city"

performance:
  # throughput: 400 # Removed: Not applicable for Serverless accounts
  autoscale: true  # Ignored by Serverless, relevant for Provisioned Throughput
  disable_indexing_during_bulk: false # Optional: Can improve write RU cost but affects reads
  sleep_interval: 60 # Seconds between polls in continuous mode

logging:
  level: "INFO" # DEBUG, INFO, WARNING, ERROR
  log_request_units: true
  log_latency: true

processing:                 # Optional: Configure data processing pipeline
  processors:               # List of processor names to apply in order
    - "SchemaValidation"    # Example: Validate required fields, convert types
    - "Sanitization"        # Example: Mask sensitive fields like sensor_id
    - "Aggregation"         # Example: Aggregate data (configure details below)
  aggregation:              # Specific configuration if "Aggregation" processor is used
    window: "1m"            # Example: Time window for aggregation (e.g., 1 minute)

```

**Processing Configuration Details:**

- **`processors`**: (list of strings, optional) Specifies the sequence of processors to apply to the data *before* uploading to Cosmos DB. The order in the list defines the execution order.
    - Available processor names might include (check source code or specific documentation for exact names and behavior):
        - `SchemaValidation`: Performs basic schema checks (e.g., required fields, data types).
        - `Sanitization`: Masks or removes sensitive information (e.g., PII).
        - `Aggregation`: Groups and aggregates data within a batch or time window (requires `aggregation` section for configuration).
- **`aggregation`**: (object, optional) Contains settings specific to the `Aggregation` processor, if used.
    - **`window`**: (string, required if `Aggregation` processor is used) Defines the time window or criteria for aggregation (e.g., `"1m"` for 1 minute). The exact format depends on the processor's implementation.

**Important:** Enabling processing stages changes the structure of the data uploaded to Cosmos DB. Ensure processors are listed in the desired order and that downstream consumers are prepared for the transformed data format resulting from the *entire* applied pipeline.

## Running the Application

1. Ensure your `cosmos-config.yaml` file is created and populated.
2. Run the application from the `cosmos-uploader` directory:

   **Standard Run (Single):**
   ```bash
   dotnet run --config path/to/cosmos-config.yaml --sqlite /path/to/your/sensor_data.db
   ```

   **Continuous Mode:**
   ```bash
   dotnet run --config path/to/cosmos-config.yaml --sqlite /path/to/your/sensor_data.db --continuous
   ```

   **Development Mode (Single Run):**
   ```bash
   dotnet run --config path/to/cosmos-config.yaml --sqlite /path/to/your/sensor_data.db --development
   ```
   *(Note: `--development` resets the 'last_write.txt' file in the SQLite database directory, which can be useful for testing and development purposes)*

### Command-Line Arguments:
- `--config`: Path to the YAML configuration file (required).
- `--sqlite`: Path to the SQLite database file (required).
- `--continuous`: Run in continuous mode, polling for new data.
- `--interval`: Interval in seconds between upload attempts in continuous mode (default: 60, uses `performance.sleep_interval` from config).
- `--archive-path`: Path to directory for archiving processed data as Parquet files (optional).
- `--development`: Enable development mode.
- `--debug`: Enable verbose debug logging (overrides config log level).

## Performance Tuning

- **Serverless**: Since this account is Serverless, focus is on optimizing RU cost per operation (e.g., via Indexing Policy) rather than tuning provisioned throughput.
- **Provisioned Throughput Accounts**: For non-Serverless accounts, adjust `performance.throughput` in the config or use Azure Portal/CLI. Consider enabling autoscale on your Cosmos container for variable workloads.
- **Direct Mode Ports**: Ensure outbound TCP ports 10250-10255 are open from the client machine/network to your Cosmos DB instance.
- **Bulk Execution**: The SDK handles optimizing requests with `AllowBulkExecution = true`. Client-side batching/parallelism limits are no longer configured.

## Logging

Configure the log `level` (`DEBUG`, `INFO`, `WARNING`, `ERROR`) and detail flags (`log_request_units`, `log_latency`) in the `logging` section of the configuration file. Use the `--debug` CLI flag to force `DEBUG` level logging.

## Troubleshooting

1. **Connection Issues**: Verify Cosmos DB endpoint/key, network connectivity (including Direct Mode ports if applicable), and container existence.
2. **Performance Issues**: Monitor RU consumption in Azure Portal. Ensure Direct Mode ports are open. Check client resource usage (CPU/memory).
3. **Data Issues**: Verify SQLite schema (`sensor_readings` table with `synced` column). Check partition key configuration. Ensure uploaded data structure matches expectations based on `processing` config.

## Contributing

Standard fork, branch, commit, push, PR workflow.

## License

MIT License - see the main project LICENSE file. 