# Edge Data Transfer Demo

## Requirements

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)

## Configuration

# Building and Running

## 1. Start the application

Build the images and start the containers:

```bash
docker-compose up -d
```

Once the application is running, open your browser and navigate to:

```
http://localhost:3000
```

## 2. Verify Instance Registration

One of the containers is client container. You can use it to check if the nodes are registered correctly with Bacalhau:

```bash
docker exec -ti edge-data-transfer-client-1 /bin/bash
```

Once you are in the client container, you can list the nodes:
```bash
bacalhau node list
```

If you see 5 nodes connected, your nodes are registered correctly.


---

**TODO**
- Change the generate job to write to /mnt/data
- Change the process_metadata job to read from /mnt/data
- Update the UI to "fake" disabling access to the NFS volume (it's not NFS anymore, but we can pretend it is)
- Update the UI to "fake" disabling access to the Bacalhau server


-----

(Didn't change anything below here)

---

## 3. Verify NFS Mount

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
