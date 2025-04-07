## How to run demo - backend?

Scripts in this example were prepared to be run in Linux environment. They use tools like base64, cat, jq (json parser).
You should have them already installed in system.


### 1. deploy infrastructure (assuming AWS credentials are defined in your system)
#### 1a. Use config that is placed in setting-up-bacalhay-network-aws-ec2-instance
It creates one FerretDB EC2 on amd64 architecture and couple Bacalhau nodes.

```yaml
(...)
  - eu-central-1:
      image: auto
      architecture: x86_64
      machine_type: t2.small
      cloud-init-scripts: "ferretdb" 		# this will instantiate FerretDB node
      node_count: 1
      tags: ferretdb_node 			# IMPORTANT - additional tag for EC2, that will allow fetch public IP address of FerretDB

  - eu-central-1: 				# it is ok to have multiple definitions of EC2 in the same region
      image: auto
      architecture: arm64 			# nodes will run on ARM64 arch
      machine_type: t4g.small
      node_count: 1 				# one node per definition, so they can have its own SENSOR_LOCATION envs
      tags: bacalhau_node
      env:
        - SENSOR_LOCATION=50.025629,8.561904	# IMPORTANT - it will be placed in sensor data as GPS location of sensor (used in Frontend)
(...)
```

#### 1b. Run script
```bash

uv run ./deploy_instances.py --action=create

# Under Linux you can also treat it as executable
./deploy_instances.py --action=create
```

After about 3 - 4 minutes (it take a bit of time to run cloud-init scripts) nodes should be accessible.

### 2. Run jobs


The script below will run daemon job that spawn sensor simulator container with location provided earlier (i.e. SENSOR_LOCATION)
```bash
chmod +x 1_run_generate_sensor_logs_job.sh

./1_run_generate_sensor_logs_job.sh
```

This will run daemon job that runs 'pusher' script, that fetches data points from sqlite and pushes them to FerretDB node.
Mind that inside the script is a part that gets FerretDB node IP address automatically (based on instance tags given earlier)

```bash
chmod +x 2_run_sync_sensor_logs_job.sh

./2_run_sync_sensor_logs_job.sh
```

The script below runs a ops job that replaces pusher script on bacalhau nodes, so they will push i.e. averaged data (in this example - every 30s)

```bash
chmod +x 3_replace_sync_sensor_logs_script.sh
./3_replace_sync_sensor_logs_script.sh
```

And the batch job that will clear all data from FerretDB node. This has no effect on any Bacalhau node that transfers the data points.
It only clears out Ferret collection that will be re-created almost immediately with new data from sensors.

```bash
chmod +x 4_run_cleanup_whole_mongodb_job.sh
./4_run_cleanup_whole_mongodb_job.sh
```

### 2. Destroy infrastructure

It is suficient to just destroy EC2 instances along with running jobs/containers
```bash
uv run ./deploy_instances.py --action destroy
```














## setting-up-bacalhau-network-aws-ec2-instance

### Changes made for FerretDB demo
 - allow to deploy arm64 or x86_64 nodes
 - util/get_ubuntu_amis.py now fetches AMI IDs for arm64 and x86_64 architectures
 - use of uv instead of plain old python pip module (faster and allows to run scripts as an 'executable')
 - dynamically sized rich console
 - different set of cloud-init scripts (for Bacalhau compute nodes and FerretDB node)
 - changed logging - log file is created instead loggin to console
 - custom tags for nodes (to distinguish i.e. between node types - visible when listing nodes)
 - creation of subnet limited by async semaphore (more thread-safe)
 - security group has 27017 port open
 - additional env variables can be passed to instance



### Running script
> **Copy config_ferret.yaml to config.yaml and enter Bacalhau token and orchestrator URL.**

#### Install uv (https://docs.astral.sh/uv/getting-started/installation/)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Make scripts executable
```bash
chmod +x util/get_ubuntu_amis.py
chmod +x deploy_instances.py
```

#### deploy infrastructure (assuming AWS credentials are defined in your system)
```bash
uv run ./deploy_instances.py --action create
```

#### list nodes
```
uv run ./deploy_instances.py --action list
```

#### destroy infrastructure
```bash
uv run ./deploy_instances.py --action destroy
```


## How to run demo frontend?

- **Environment Variables:** Sets `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` and `MONGODB_IP` via build arguments.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your machine.
- (Optional) [Docker Compose](https://docs.docker.com/compose/install/) if you want to use the provided `docker-compose.yml`.

## Files

- **Dockerfile:** Contains instructions for building the Docker image.
- **package.json** and **package-lock.json:** NPM configuration files for the Next.js application.
-
## Environment Variables

Before building the Docker image, make sure to set the required environment variables:

### 1. `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`

- This variable is required to use Google Maps services in the frontend.
- You need to [generate an API key from the Google Cloud Console](https://console.cloud.google.com/apis/credentials) and enable the **Maps JavaScript API**.
- Paste your key into the `.env` file or pass it as a build argument.

### 2. `MONGODB_IP`

- Set this to the IP address or hostname of your FerretDB Node.
- Example: `127.0.0.1`.

#### Create a .env file in the project directory with the following content:
```dotenv
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_google_maps_api_key
MONGODB_IP=your_mongodb_ip
```

## Start the container using Docker Compose
```bash
docker compose up
```
