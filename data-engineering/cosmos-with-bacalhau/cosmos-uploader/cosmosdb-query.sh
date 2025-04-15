#!/bin/bash
set -e

# Simple bash script to query CosmosDB directly

# Default values
CONFIG_PATH=""
COSMOS_ENDPOINT=""
COSMOS_KEY=""
COSMOS_DATABASE=""
COSMOS_CONTAINER=""
COSMOS_RESOURCE_GROUP=""
QUERY="SELECT * FROM c LIMIT 10"
COUNT=false
CITY=""
SENSOR=""
LIMIT=10

# Show help and exit
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Query CosmosDB to check if data is being uploaded properly"
    echo
    echo "Options:"
    echo "  --config CONFIG_FILE    Path to config YAML file (optional)"
    echo "  --endpoint URL          CosmosDB endpoint URL"
    echo "  --key KEY               CosmosDB access key"
    echo "  --database NAME         Database name"
    echo "  --container NAME        Container name"
    echo "  --count                 Count total documents"
    echo "  --city CITY             Filter by city (partition key)"
    echo "  --sensor SENSOR_ID      Filter by sensor ID"
    echo "  --limit N               Limit results (default: 10)"
    echo "  --query 'SQL QUERY'     Execute a custom SQL query"
    echo "  --help, -h              Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --config /Users/daaronch/code/bacalhau-examples/data-engineering/cosmos-with-bacalhau/config/config.yaml --count"
    echo "  $0 --config config/config.yaml --city Amsterdam --limit 5"
    echo "  $0 --endpoint \$COSMOS_ENDPOINT --key \$COSMOS_KEY --database SensorData --container SensorReadings --city Amsterdam"
    echo
    exit 0
}

# Process arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --endpoint)
            COSMOS_ENDPOINT="$2"
            shift 2
            ;;
        --key)
            COSMOS_KEY="$2"
            shift 2
            ;;
        --database)
            COSMOS_DATABASE="$2"
            shift 2
            ;;
        --container)
            COSMOS_CONTAINER="$2"
            shift 2
            ;;
        --count)
            COUNT=true
            shift
            ;;
        --city)
            CITY="$2"
            shift 2
            ;;
        --sensor)
            SENSOR="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --query)
            QUERY="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Check if we need to load from config file
if [ -n "$CONFIG_PATH" ]; then
    if [ ! -f "$CONFIG_PATH" ]; then
        echo "Error: Config file not found at $CONFIG_PATH"
        exit 1
    fi
    
    echo "Loading configuration from $CONFIG_PATH..."
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is required but not installed"
        exit 1
    fi
    
    # Install PyYAML if needed
    if ! python3 -c "import yaml" &> /dev/null; then
        echo "Installing PyYAML..."
        python3 -m pip install pyyaml --quiet
    fi
    
    # Extract values from YAML
    CONFIG=$(python3 -c "
import yaml, sys, os
try:
    with open('$CONFIG_PATH', 'r') as f:
        config = yaml.safe_load(f)
    cosmos = config.get('cosmos', {})
    print(f\"COSMOS_ENDPOINT={cosmos.get('endpoint', '')}\")
    print(f\"COSMOS_KEY={cosmos.get('key', '')}\")
    print(f\"COSMOS_DATABASE={cosmos.get('database_name', '')}\")
    print(f\"COSMOS_CONTAINER={cosmos.get('container_name', '')}\")
    print(f\"COSMOS_RESOURCE_GROUP={cosmos.get('resource_group', '')}\")
except Exception as e:
    print(f'Error loading config: {e}', file=sys.stderr)
    sys.exit(1)
")
    
    # Load the values
    eval "$CONFIG"
fi

# Check for environment variables
COSMOS_ENDPOINT=${COSMOS_ENDPOINT:-$COSMOS_ENDPOINT_ENV}
COSMOS_KEY=${COSMOS_KEY:-$COSMOS_KEY_ENV}
COSMOS_DATABASE=${COSMOS_DATABASE:-$COSMOS_DATABASE_ENV}
COSMOS_CONTAINER=${COSMOS_CONTAINER:-$COSMOS_CONTAINER_ENV}
COSMOS_RESOURCE_GROUP=${COSMOS_RESOURCE_GROUP:-$COSMOS_RESOURCE_GROUP_ENV}

# Validate required fields
if [ -z "$COSMOS_ENDPOINT" ] || [ -z "$COSMOS_KEY" ] || [ -z "$COSMOS_DATABASE" ] || [ -z "$COSMOS_CONTAINER" ]; then
    echo "Error: Missing required CosmosDB connection parameters"
    echo "Please provide either a config file or all connection parameters"
    exit 1
fi

# Check if we have the Azure CLI
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI (az) is required but not installed"
    echo "Please install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if cosmos extension is installed
if ! az cosmosdb --help &> /dev/null; then
    echo "Installing Azure CLI CosmosDB extension..."
    az extension add --name cosmosdb-preview
fi

# Check available commands for sql container
echo "Checking available Azure CLI cosmosdb sql container commands..."
az cosmosdb sql container --help | grep -A 20 "Commands:"

# Build the query if needed
if [ "$QUERY" = "SELECT * FROM c LIMIT 10" ] && { [ -n "$CITY" ] || [ -n "$SENSOR" ]; }; then
    QUERY="SELECT * FROM c WHERE 1=1"
    
    if [ -n "$CITY" ]; then
        QUERY="$QUERY AND c.city = '$CITY'"
    fi
    
    if [ -n "$SENSOR" ]; then
        QUERY="$QUERY AND c.sensorId = '$SENSOR'"
    fi
    
    QUERY="$QUERY LIMIT $LIMIT"
fi

# Handle count query
if [ "$COUNT" = true ]; then
    QUERY="SELECT VALUE COUNT(1) FROM c"
fi

echo "Executing query: $QUERY"
echo "on database: $COSMOS_DATABASE, container: $COSMOS_CONTAINER"

# Extract the account name from the endpoint URL
ACCOUNT_NAME=$(echo "$COSMOS_ENDPOINT" | sed -E 's/https:\/\/([^.]+).*/\1/')
if [ -z "$ACCOUNT_NAME" ]; then
    echo "Error: Could not parse account name from endpoint: $COSMOS_ENDPOINT"
    exit 1
fi

echo "Account name: $ACCOUNT_NAME"

# Use resource group from config if available, otherwise look it up
if [ -z "$COSMOS_RESOURCE_GROUP" ]; then
    echo "Looking up resource group from Azure..."
    RESOURCE_GROUP=$(az cosmosdb list --query "[?name == '$ACCOUNT_NAME'].resourceGroup" -o tsv)
    if [ -z "$RESOURCE_GROUP" ]; then
        echo "Error: Could not find resource group for account: $ACCOUNT_NAME"
        echo "Make sure you're logged in with 'az login' and have access to this account"
        exit 1
    fi
else
    RESOURCE_GROUP="$COSMOS_RESOURCE_GROUP"
    echo "Using resource group from config: $RESOURCE_GROUP"
fi

# Execute the query
echo "Executing query..."
echo "Using command: az cosmosdb sql container query"
echo "Params:"
echo "  --resource-group: $RESOURCE_GROUP"
echo "  --account-name: $ACCOUNT_NAME"
echo "  --database-name: $COSMOS_DATABASE"
echo "  --name: $COSMOS_CONTAINER"
echo "  --query: $QUERY"

# Run command with error handling
set +e  # Turn off exit on error temporarily
result=$(az cosmosdb sql container query \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$ACCOUNT_NAME" \
    --database-name "$COSMOS_DATABASE" \
    --name "$COSMOS_CONTAINER" \
    --query "$QUERY" \
    --output json 2>&1)
exit_code=$?
set -e  # Turn back on exit on error

if [ $exit_code -ne 0 ]; then
    echo "Error executing query. Exit code: $exit_code"
    echo "Error message: $result"
    
    # Check if the command itself is invalid
    if [[ "$result" == *"'query' is misspelled or not recognized"* ]]; then
        echo "The 'query' command might not be available in your Azure CLI version."
        echo "Trying alternative command format..."
        
        # Try alternative command format
        result=$(az cosmosdb sql query \
            --resource-group-name "$RESOURCE_GROUP" \
            --account-name "$ACCOUNT_NAME" \
            --database-name "$COSMOS_DATABASE" \
            --container-name "$COSMOS_CONTAINER" \
            --query-text "$QUERY" \
            --output json 2>&1)
        exit_code=$?
        
        if [ $exit_code -ne 0 ]; then
            echo "Alternative command also failed with exit code: $exit_code"
            echo "Error message: $result"
            exit 1
        fi
    else
        # Other error
        exit 1
    fi
fi

# Process results
echo "Processing results..."
if [[ "$result" == *"Error"* || "$result" == *"error"* || "$result" == *"Failed"* ]]; then
    echo "Error in response:"
    echo "$result"
    exit 1
fi

# Check if result is valid JSON
if ! echo "$result" | python3 -c "import json, sys; json.load(sys.stdin)" &> /dev/null; then
    echo "Warning: Response is not valid JSON:"
    echo "$result"
    exit 1
fi

if [ "$COUNT" = true ]; then
    # Extract the count value
    count=$(echo "$result" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if isinstance(data, list) and len(data) > 0:
        print(data[0])
    else:
        print('Error: Unexpected response format')
except Exception as e:
    print(f'Error parsing count result: {e}', file=sys.stderr)
    print(sys.stdin.read())
")
    echo "Total document count: $count"
else
    # Pretty print the results
    echo "$result" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data:
        print('No documents found')
    elif isinstance(data, list):
        print(f'Found {len(data)} documents:')
        for i, doc in enumerate(data):
            print(f'\\nDocument {i+1}:')
            print(json.dumps(doc, indent=2))
    else:
        print('Warning: Unexpected response format')
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f'Error parsing results: {e}', file=sys.stderr)
    print(sys.stdin.read())
"
fi

echo "Query completed successfully"