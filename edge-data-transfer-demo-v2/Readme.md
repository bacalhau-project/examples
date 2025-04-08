# Edge Data Transfer Demo

In the built backend Docker image, there is already Midnight Commander installed, so it could be used 
to ease configuration changes.

## Requirements

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)
- A `.env` file containing the necessary environment variables (see Configuration section)

## Configuration

Before running the project, create a `.env` file in the root directory (where the `docker-compose.yml` file is located) with the following content:

```env
BACALHAU_API_HOST=https://<bacalhau_api_host>
BACALHAU_API_KEY=<your bacalhau api key>
BACALHAU_API_TLS_USETLS=true

COMPUTE_AUTH_TOKEN=<your bacalhau compute node auth token>
COMPUTE_ORCHESTRATOR=nats://<your bacalhau orchestrator>:4222
COMPUTE_AWS_REGION=us-west-1
```

> **Note:** 
> You can use variables that will be presented to you in cloud.expanso.io while creating new network.
> Just create new network and then add node. Configuration variables can be displayed in portal.
---

# Building and Running

## 1. Start the application

Build the images and start the containers:

```bash
docker-compose up --build -d
```

> **Note:** Newest version of compose is incorporated in Docker itself and the command is called without a dash


Once the application is running, open your browser and navigate to:

```
http://localhost:3000
```

---

## 2. Backend Setup

### Access the backend container:

```bash
docker exec -it edge-data-transfer-demo-backend-1 /bin/bash
```

### Configure AWS credentials:

Inside the container, run:

```bash
aws configure
```

Provide your AWS Access Key, Secret Access Key, region, and output format.

### Fetch the latest Ubuntu AMIs:

> **Note:** This step is optional and configuration could be left as is, as long as already fetched AMI images are working properly.

```bash
uv run -s util/get_ubuntu_amis.py
```

#### View the downloaded AMIs:

```bash
cat ubuntu_amis.csv
```

Choose the appropriate AMI(s) for your region and use case.

---

## 3. Update Configuration

In order to create example configuration you can use /backend/generate_example_config.sh script.
Run these commands in backend container 
```bash
chmod +x generate_example_config.sh
./generate_example_config.sh
```
This will overwrite existing config.yaml_example file with provided environment variables for you.

You can then change machine type or number of nodes to instantiate.
Once reviewed, example file can be used as config.yaml

```bash
cp config.yaml_example config.yaml
```

---

## 4. Deploy Spot Instances

To create the Spot instances:

```bash
uv run -s ./deploy_spot.py create
```
This step will deploy EC2 instances and create EFS share, used in demo.

> **Note:** In case of any problems see debug.log file in /backend folder.

---

## 5. Verify Instance Registration

In the backend container, check that the new nodes have registered correctly with Bacalhau:

```bash
bacalhau node list
```

You should see your Spot instances listed as active nodes.

---

## 6. Verify NFS Mount

SSH into one of the Spot instances.

The private ssh key for the machines is located in the /root/.ssh/id_rsa directory on backend docker.

By default user in nodes is 'bacalhau-runner'. The public IP address of node could be seen in labels while listing bacalhau nodes.

```bash
ssh bacalhau-runner@<node's public ip>
```
 and verify that the NFS volume is mounted.
```bash
df -h
```

You should see `/mnt/data` listed in the output.

---

## 7. Generate Test Data

Submit a job to generate random test files:
Jobs are available in the /backend/job directory
```bash
bacalhau job run generate.yaml
```

> **Warning:** This job can take up to 40 minutes. After a 5 minutes you'll see timeout while tracking job execution but job itself is running on network.

---

## 8. Run Metadata Generation Job

Submit the main processing job to generate metadata:

```bash
bacalhau job run process_metadata.yaml
```

## 9. Cleanup

After demo, you can destroy EC2 instances by running 

```bash
uv run -s ./deploy_spot.py destroy
```
in backend container.

You should also delete data from EFS share and EFS itself.
