# CosmosDB Query Tool

This tool allows you to query Azure Cosmos DB directly to verify if data is being uploaded correctly.

## Prerequisites

- Python 3.11 or later
- UV package manager (automatically used by the script)
- Access to an Azure Cosmos DB account

## Usage

```bash
# Run the tool directly with UV
uv run -s cosmos-uploader/query.py [OPTIONS]
```

## Options

### Connection options
- `--config CONFIG_FILE` - Path to the config file
- `--endpoint URL` - CosmosDB endpoint URL
- `--key KEY` - CosmosDB access key
- `--database NAME` - Database name
- `--container NAME` - Container name

### Query options
- `--count` - Count total documents
- `--city CITY` - Filter by city (partition key)
- `--sensor SENSOR_ID` - Filter by sensor ID
- `--limit N` - Limit results (default: 10)
- `--query 'SQL QUERY'` - Execute a custom SQL query
- `--format` - Output format (`json` or `table`)
- `--analyze` - Analyze data distribution

### Data management options
- `--clear` - Clear documents from the container
- `--filter 'CONDITION'` - Filter condition for clearing data (e.g. `c.city="London"`)
- `--dry-run` - Show what would be deleted without actually deleting
- `--force-delete` - Force deletion without dry run (use with caution)
- `--no-sproc` - Disable using stored procedure for deletion (slower but more compatible)

### Other options
- `--verbose, -v` - Show verbose output
- `--help, -h` - Show help message

## Examples

1. Count all documents:
   ```bash
   uv run -s cosmos-uploader/query.py --config config/config.yaml --count
   ```

2. Filtering by city with a limit:
   ```bash
   uv run -s cosmos-uploader/query.py --config config/config.yaml --city Amsterdam --limit 5
   ```

3. Using a custom query:
   ```bash
   uv run -s cosmos-uploader/query.py --config config/config.yaml --query "SELECT TOP 5 * FROM c WHERE c.temperature > 25.0"
   ```

4. Analyze data distributions:
   ```bash
   uv run -s cosmos-uploader/query.py --config config/config.yaml --analyze
   ```

5. Show results in table format:
   ```bash
   uv run -s cosmos-uploader/query.py --config config/config.yaml --format table
   ```

6. Clear data for a specific city (with dry run first):
   ```bash
   # First do a dry run to see what would be deleted
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --city London --dry-run
   
   # Then actually delete if the dry run looks correct
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --city London
   ```

7. Clear all data with custom filter:
   ```bash
   # Delete all records where temperature is above 80
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --filter 'c.temperature > 80'
   ```

8. Use stored procedure for high-performance deletion (much faster):
   ```bash
   # Using stored procedure (default)
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --city Amsterdam
   
   # Force using client-side deletion if the stored procedure doesn't work
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --city Amsterdam --no-sproc
   ```

9. Delete all data (USE WITH CAUTION):
   ```bash
   # First count to see how many documents will be affected
   uv run -s cosmos-uploader/query.py --config config/config.yaml --count
   
   # Then run with dry-run first (default for safety)
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear
   
   # Finally, force delete all documents
   # THIS WILL DELETE EVERYTHING!
   uv run -s cosmos-uploader/query.py --config config/config.yaml --clear --force-delete
   ```

## Troubleshooting

- **Connection Issues**: Make sure your Cosmos DB connection string, key, and endpoint are correct.
- **No Results**: Verify that data is actually being uploaded by checking the sensor containers.
- **Permission Issues**: Make sure the account has read permissions on the Cosmos DB container.

## Features

The Python-based tool offers several improvements over the Bash script:

1. **Better Error Handling**: More descriptive error messages with proper diagnostics
2. **Environment Variable Expansion**: Supports `${ENV_VAR}` and `${ENV_VAR:-default}` syntax
3. **Data Analysis**: Added `--analyze` flag to provide a summary of data distribution
4. **Table Output**: Added `--format table` option for more readable output
5. **Progress Indication**: Visual progress indicators during operations
6. **Automatic Dependency Management**: Uses UV to install required dependencies