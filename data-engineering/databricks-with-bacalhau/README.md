# Cosmos DB with Bacalhau

This project demonstrates how to use Azure Cosmos DB with Bacalhau for data engineering workloads. It includes tools for processing sensor data from SQLite databases and uploading it efficiently to Cosmos DB.

## Environment Variables
Before proceeding, export the following environment variables in your shell:

- export S3_BUCKET_NAME=<your-s3-bucket-name>
- export AWS_REGION=<your-aws-region>
- export AWS_PROFILE=<your-aws-cli-profile>       # optional, if using a named CLI profile

If not using instance profiles for remote-node uploads, also set:

- export AWS_ACCESS_KEY_ID=<your-access-key-id>
- export AWS_SECRET_ACCESS_KEY=<your-secret-access-key>

## Project Structure

- `cosmos-uploader/`: Contains the C# application for uploading data to Cosmos DB.
- `config/`: Configuration files for the uploader and simulation (if used).
- `data/`: Directory intended for storing sensor data in SQLite databases.
  - `{city}/{sensor-number}/`: Example structure for SQLite database files.
- `archive/`: Directory intended for archiving processed data.
  - `{city}/`: Example structure for Parquet archive files.
- `sensor_manager/`: Python-based sensor manager/simulator (optional).
 - `utility_scripts/`: Miscellaneous helper scripts.

## Roadmap & Next Steps

This project follows a re-architecture plan to transition Bacalhau job results to the Databricks Lakehouse. For the full plan and progress checklist, see [REARCHITECTURE.md](REARCHITECTURE.md).

**Next Immediate Step:** Configure and test the secure connection from Databricks to AWS S3 (Phase 1.2.2 in the roadmap).
See [Databricks S3 Connectivity Guide](docs/databricks-s3-connect.md) for a sample notebook snippet.

## Build Commands

- Build C# application: `cd cosmos-uploader && ./build.sh [--tag VERSION] [--no-tag]`
- Run cosmos query: `cd cosmos-uploader && uv run query.py --config path/to/cosmos-config.yaml [options]`
- Run sensor manager (Python): `./sensor_manager.py [command] [options]`
  - Example commands: `start`, `stop`, `reset`, `clean`, `build`, `logs`, `query`, `diagnostics`, `monitor`, `cleanup`

## Data Flow and Structure

1.  **Sensor Simulation (Optional)**: `sensor_manager` can generate sensor readings (`{CITY}_{SENSOR_CODE}`) stored locally in SQLite DBs.
2.  **Uploader**: The `cosmos-uploader` reads from SQLite, uploads to Cosmos DB, and optionally archives processed data to Parquet.

### Directory Structure (Expected)

```
/
├── config/                  # Configuration files
├── data/                    # Root for raw sensor data
│   ├── London/              # City-level directory
│   │   ├── abc123/          # Sensor-specific directory
│   │   │   └── sensor_data.db # Raw data
│   │   ├── def456/
│   │   │   └── sensor_data.db
│   │   └── ...
│   ├── Paris/
│   │   └── ...
│   └── ...
├── archive/                 # Root for processed data archives
│   ├── London/              # City-level directory
│   │   ├── abc123.parquet   # Archived data per sensor
│   │   ├── def456.parquet
│   │   └── ...
│   ├── Paris/
│   │   └── ...
│   └── ...
└── ... (project code like cosmos-uploader/, sensor_manager/, etc.)
```

- **City-based organization**: Data and archives are organized by city.
- **Sensor-based identification**: SQLite data is stored per-sensor; Parquet archives consolidate data per sensor over time.
- **Uploader Isolation**: The uploader (when run per city, e.g., by `sensor_manager`) typically only accesses its assigned city's `data/` and `archive/` subdirectories.

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
            *(Note the `nameserver` IP addresses listed, e.g., `1.1.1.1`)*
        4.  Attempt to resolve the Cosmos DB endpoint using the container's configured DNS:
            ```bash
            nslookup your-cosmos-account.documents.azure.com
            ```
            *(Replace with your actual endpoint. Timeouts or failures here indicate a DNS problem.)*
        5.  Test connectivity to the DNS server itself (use an IP from `resolv.conf`):
            ```bash
            ping -c 3 1.1.1.1
            traceroute -T -p 53 1.1.1.1 # Test UDP port 53 connectivity
            ```
            *(`traceroute` stopping with `* * *` can indicate where the block occurs.)*
    *   **Likely Cause**: Outbound network traffic on UDP port 53 (used for DNS lookups) is being blocked by a firewall rule. This block could be on the host machine's firewall (e.g., `iptables`), an external firewall, or a cloud Network Security Group (NSG). Docker containers rely on external DNS resolution.
    *   **Solutions**:
        1.  **(Recommended)** **Adjust External Firewall/NSG**: Modify the outbound rules for the host machine (where Docker is running) to ALLOW UDP traffic on destination port 53, originating from the host's IP address, to the required DNS server IPs (e.g., `1.1.1.1`, `1.0.0.1`) or to `0.0.0.0/0` for general DNS access.
        2.  **(Workaround)** **Configure Docker Daemon DNS**: Configure the Docker daemon to use a specific DNS server (e.g., `1.1.1.1`).

## Cloud Storage & Databricks Foundation Setup (AWS S3)

The new architecture targets Bacalhau job outputs → AWS S3 bucket → Databricks Lakehouse.

### 1. AWS S3 Bucket Provisioning

1. Install and configure AWS CLI:
   ```bash
   pip install awscli
   aws configure
   ```
2. Create an S3 bucket (using `$S3_BUCKET_NAME` and `$AWS_REGION`):
   ```bash
   aws s3api create-bucket \
     --bucket $S3_BUCKET_NAME \
     --region $AWS_REGION \
     --create-bucket-configuration LocationConstraint=$AWS_REGION
   ```
3. (Optional) Enable versioning and lifecycle policies:
   ```bash
   aws s3api put-bucket-versioning \
     --bucket $S3_BUCKET_NAME \
     --versioning-configuration Status=Enabled

   aws s3api put-bucket-lifecycle-configuration \
     --bucket $S3_BUCKET_NAME \
     --lifecycle-configuration '{
       "Rules": [
         {
           "ID": "cleanup-old-data",
          "Prefix": "",
           "Status": "Enabled",
           "Expiration": {"Days": 365}
         }
       ]
     }'
   ```

### 2. Designing a Folder Structure

For simplicity, store all Parquet output files flat at the bucket root, named by sensor ID:
```
s3://$S3_BUCKET_NAME/<SENSOR_ID>.parquet
```

### 3. IAM Roles & Credentials

#### 3.1 Remote Node Upload Role
- Create an IAM role or user with an inline policy granting PutObject/ListBucket on the bucket path.
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:PutObject", "s3:ListBucket"],
        "Resource": [
          "arn:aws:s3:::${S3_BUCKET_NAME}",
          "arn:aws:s3:::${S3_BUCKET_NAME}/*"
        ]
      }
    ]
  }
  ```
- For non-AWS hosts, configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.

#### 3.2 Databricks Access via Instance Profile
1. In AWS IAM, create an instance profile role with the same S3 read permissions.
2. In Databricks account console, configure the role as a cluster IAM role (Instance Profile).
3. Attach the instance profile to your Databricks cluster.

#### 3.3 Unity Catalog IAM Role Setup
Below are AWS CLI commands to create an IAM role with the permissions needed for Unity Catalog and to verify setup.

1. (If not already created) Create the S3 bucket:
```bash
aws s3api create-bucket \
  --bucket $S3_BUCKET_NAME \
  --region $AWS_REGION \
  --create-bucket-configuration LocationConstraint=$AWS_REGION
```

2. Create an IAM trust policy for Databricks (save as `trust-policy.json`).
Replace `414351767826` with the Databricks AWS account ID for your region, and `YOUR_DATABRICKS_ACCOUNT_ID` with your Databricks account ID.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::414351767826:root" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "sts:ExternalId": "YOUR_DATABRICKS_ACCOUNT_ID" }
      }
    }
  ]
}
```

3. Create the IAM role:
```bash
aws iam create-role \
  --role-name DatabricksUnityCatalogRole \
  --assume-role-policy-document file://trust-policy.json
```

4. Create an IAM policy for S3 access (save as `uc-s3-policy.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
        "s3:ListBucket", "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::$S3_BUCKET_NAME",
        "arn:aws:s3:::$S3_BUCKET_NAME/*"
      ]
    }
  ]
}
```

5. Attach the policy to the role:
```bash
aws iam put-role-policy \
  --role-name DatabricksUnityCatalogRole \
  --policy-name DatabricksUnityCatalogS3Access \
  --policy-document file://uc-s3-policy.json
```

6. Retrieve the role ARN (for use in the Databricks metastore):
```bash
aws iam get-role --role-name DatabricksUnityCatalogRole --query 'Role.Arn' --output text
```

7. (Optional) Enable S3 bucket versioning:
```bash
aws s3api put-bucket-versioning \
  --bucket $S3_BUCKET_NAME \
  --versioning-configuration Status=Enabled
```

**Verification:**
- Check the bucket exists:
  ```bash
  aws s3 ls s3://$S3_BUCKET_NAME
  ```
- Verify the role policy:
  ```bash
  aws iam get-role-policy \
    --role-name DatabricksUnityCatalogRole \
    --policy-name DatabricksUnityCatalogS3Access
  ```

Use the S3 path `s3://$S3_BUCKET_NAME/unity-catalog` (or a subpath) and the Role ARN from step 6 when configuring Unity Catalog in Databricks.

### 4. Configuring Databricks

#### 4.1 Secret Scopes (if using keys)
```bash
databricks secrets create-scope --scope aws-credentials
databricks secrets put --scope aws-credentials --key aws_access_key_id
databricks secrets put --scope aws-credentials --key aws_secret_access_key
```

#### 4.2 Spark Configuration (Cluster init script or Notebook)
```python
spark.conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
spark.conf.set("spark.hadoop.fs.s3a.access.key", dbutils.secrets.get("aws-credentials","aws_access_key_id"))
spark.conf.set("spark.hadoop.fs.s3a.secret.key", dbutils.secrets.get("aws-credentials","aws_secret_access_key"))
# optional optimizations:
spark.conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
```

#### 4.3 Accessing Data in Notebooks
```python
# Reading Parquet
df = spark.read.parquet("s3a://$S3_BUCKET_NAME/<SENSOR_ID>.parquet")
display(df)

# Using Auto Loader (cloudFiles)
df_stream = (
  spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "parquet")
    .option("cloudFiles.schemaLocation", "s3a://$S3_BUCKET_NAME/_schemas/")
    .load("s3a://$S3_BUCKET_NAME/")
)
df_stream.writeStream.format("delta") \
    .option("checkpointLocation", "s3a://$S3_BUCKET_NAME/_checkpoints/") \
    .toTable("bacalhau_results")
```

#### 4.4 Setting Up Delta Lake Tables

Before running your Auto Loader jobs, ensure the target Delta Lake table exists on Databricks. In a notebook or the SQL editor, run:
```sql
-- Create a database/schema if needed
CREATE DATABASE IF NOT EXISTS bacalhau_results
  LOCATION 's3a://$S3_BUCKET_NAME/delta/bacalhau_results';

-- Create a Delta table for sensor readings
CREATE TABLE IF NOT EXISTS bacalhau_results.sensor_readings
USING DELTA
LOCATION 's3a://$S3_BUCKET_NAME/delta/bacalhau_results';
```
If using Unity Catalog, register in your catalog instead:
```sql
CREATE SCHEMA IF NOT EXISTS catalog_name.bacalhau_results;
CREATE TABLE IF NOT EXISTS catalog_name.bacalhau_results.sensor_readings
USING DELTA
LOCATION 's3a://$S3_BUCKET_NAME/delta/bacalhau_results';
```
This setup guarantees your ingestion jobs have a pre-existing Delta Lake target.

### 5. Next Steps

- Implement Bacalhau job output to Parquet on remote nodes.
- Build a resilient upload script that writes to the S3 path.
- Develop Databricks Auto Loader notebooks to ingest and write Delta tables.
- Set up Databricks Workflows for orchestration.

## License

MIT License - see the LICENSE file for details.