# Edge Data Transfer Demo

In the built image, there is already Midnight Commander installed so it could be used 
to ease configuration changes.

## Requirements

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)
- A `.env` file containing the necessary environment variables (see Configuration section)

## Configuration

Before running the project, create a `.env` file in the root directory (where the `docker-compose.yml` file is located) with the following content:

```env
BACALHAU_TOKEN=your_client_token
BACALHAU_API_HOST=api_host
BACALHAU_API_TLS_USETLS=true
```

> **Note:** You can obtain the `BACALHAU_TOKEN` and `BACALHAU_API_HOST` from Expanso Cloud.

Bacalhau API host should be entered without protocol and port. These will be added internally.

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
docker exec -it edge-data-transfer-demo_backend_1 /bin/bash
```

### Configure AWS credentials:

Inside the container, run:

```bash
aws configure
```

Provide your AWS Access Key, Secret Access Key, region, and output format.

### Fetch the latest Ubuntu AMIs:

This step is optional and configuration could be left as is, as long as already fetched
AMI images are working properly.

```bash
uv run -s util/get_ubuntu_amis.py
```

### View the downloaded AMIs:

```bash
cat ubuntu_amis.csv
```

Choose the appropriate AMI(s) for your region and use case.

---

## 3. Update Configuration

Edit the `config.yaml` file to include the selected AMI(s) and set the following fields:

- `orchestrators`
- `server_token`

If you want to change the spot size you need to change the

- `machine_type`

---

## 4. Deploy Spot Instances

To create the Spot instances:

```bash
uv run -s ./deploy_spot.py create
```
This step will deploy EC2 instances and create EFS share, used in demo.

---

## 5. Verify Instance Registration

In the backend container, check that the new nodes have registered correctly with Bacalhau:

```bash
echo $BACALHAU_TOKEN | bacalhau node list
```

You should see your Spot instances listed as active nodes.

---

## 6. Verify NFS Mount

SSH into one of the Spot instances.

The private ssh key for the machines is located in the /root/.ssh/id_rsa directory on backend docker.

By default user in nodes is 'bacalhau-runner'. The public IP addres of node could be seen in labels while listing bacalhau nodes.

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

You should also delete data from EFS share.
