# Cosmos Uploader

A .NET 10.0 application for efficiently uploading data to Azure Cosmos DB. This tool supports batch processing and parallel operations for optimal performance.

## Prerequisites

- [.NET 10.0 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
- Azure Cosmos DB account with appropriate access credentials
- SQLite (for local data storage)

## Building the Application

1. Navigate to the cosmos-uploader directory:
   ```bash
   cd cosmos-uploader
   ```

2. Restore dependencies and build the application:
   ```bash
   dotnet restore
   dotnet build
   ```

## Configuration

The application uses a YAML configuration file. Create a `cosmos-config.yaml` file in the project root with the following structure:

```yaml
# Cosmos DB Configuration
cosmos:
  endpoint: "https://your-cosmos-account.documents.azure.com:443/"
  key: "your-cosmos-key"
  database: "SensorData"
  container: "SensorReadings"
  partition_key: "/city"

# Performance Settings
performance:
  throughput: 400
  batch_size: 100
  max_parallel_operations: 10

# Logging Configuration
logging:
  level: "INFO"
  log_request_units: true
  log_latency: true

# Configuration File Watch Settings
config_watch:
  enabled: true
  poll_interval_seconds: 5
```

## Running the Application

1. Create your `cosmos-config.yaml` file with the appropriate settings.

2. Run the application:
   ```bash
   dotnet run --config cosmos-config.yaml --sqlite /path/to/sqlite
   ```

The application supports the following command-line arguments:
- `--config`: Path to the YAML configuration file (required)
- `--sqlite`: Directory containing SQLite databases (required)
- `--continuous`: Run in continuous mode, polling for new data
- `--interval`: Interval in seconds between upload attempts in continuous mode (default: 60)
- `--archive-path`: Path to archive uploaded data

## Configuration File Watching

The application automatically watches the configuration file for changes. When changes are detected:
- The configuration is reloaded
- The new settings are applied
- A log message is generated

You can configure the watch behavior in the `config_watch` section of your YAML file:
- `enabled`: Enable/disable configuration watching
- `poll_interval_seconds`: How often to check for changes

## Performance Tuning

The application includes several performance-related settings in the YAML configuration:

- `throughput`: RU/s allocated for the container
- `batch_size`: Number of items processed in each batch
- `max_parallel_operations`: Maximum number of parallel operations

Adjust these settings based on your specific requirements and Cosmos DB capacity.

## Logging

The application uses Microsoft.Extensions.Logging with the following configuration options in the YAML file:

- `level`: Log level (INFO, DEBUG, WARNING, ERROR)
- `log_request_units`: Enable/disable RU consumption logging
- `log_latency`: Enable/disable operation latency logging

## Troubleshooting

1. Connection Issues:
   - Verify your Cosmos DB endpoint and key in the YAML configuration
   - Check network connectivity
   - Ensure the Cosmos DB account is accessible

2. Performance Issues:
   - Monitor RU consumption
   - Adjust batch size and parallel operations in the YAML configuration
   - Check network latency

3. Data Issues:
   - Verify data format and schema
   - Check partition key configuration in the YAML file
   - Monitor error logs for specific issues

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 