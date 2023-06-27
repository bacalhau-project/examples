# Instructions to Running with MotherDuck

## Introduction
This example shows how to run a simple log processing pipeline with MotherDuck. The pipeline consists of two components:
* A container that runs a python script that generates logs
* A container that runs a python script that processes logs and uploads them to MotherDuck

You will also have to login with credentials for Google Cloud, and Tailscale.

## Setting up your .env.json file.
In the `terraform` directory, there is a file called `.env.json.example`. Copy this file to `.env.json` and fill in the values. The explanation for all the values are as follows:
* project_id - GCP project ID for the project
* bootstrap_zone: Zone where the bootstrap node for the network will be created
* locations - a set of objects that define the locations of the nodes in the cluster. Each object has the following fields:
  * key for each entry - the name of the zone
  * region - the name of the region
  * storage_location - the location of the storage bucket for the node (if needed)
* motherduck_key: The API key from motherduck - apply here [app.motherduck.com](app.motherduck.com)
* tailscale_key: An auth key from Tailscale. You can get one from [https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys). It should be "Reusable", "Expiration of 90 days", "Ephemeral" and have a tag of something meaningful to you.
* app_name: A meaningful & unique name - will be used as a prefix on the logs.
* bacalhau_run_file: When Bacalhau starts on the bootstrap node, it creates a `bacalhau.run` file. This file contains the information needed to connect to the cluster. This field specifies the name (but not location) of that file. It will be created in the `/run` directory (unless the installer does not have permissions). During the installation, the file will be copied to the `terraform` directory for installation in non-bacalhau nodes.
* username: The username to use for the nodes - will be added to `sudoers` and be the account needed to ssh into the nodes (should not be necessary).
* public_key: Location of the public key for the account for logging in (e.g. ~/.ssh/id_rsa.pub)
* private_key: Location of the private key for the account for logging in (e.g. ~/.ssh/id_rsa)
* app_tag:  This will be used to group manage the resources created by this script (e.g. delete them all at once)


## Setting up Google Cloud
First, you need to install the Google Cloud SDK. Depending on your platform, you will need to install from a package manager, or directly compile. Instructions to do so are here. [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

After installing, you need to login to your Google Cloud account. [Full Instructions](https://cloud.google.com/sdk/docs/initializing). For most platforms, you should simply type:
```bash
gcloud auth login
```

After logging in, you need to create a project. [Full Instructions](https://cloud.google.com/resource-manager/docs/creating-managing-projects).

```bash
PROJECT_ID="my-project"
gcloud projects create $PROJECT_ID
```

You also need to get your billing account ID. 

```bash
gcloud beta billing accounts list
BILLING_ACCOUNT_ID="0136BA-110539-DCE35A"
```

Finally, you need to link the billing account to the project. [Full Instructions](https://cloud.google.com/billing/docs/how-to/modify-project).
  
```bash
gcloud beta billing projects link $PROJECT_ID --billing-account $BILLING_ACCOUNT_ID
```

Finally, you need to enable the compute API and storage API. [Full Instructions](https://cloud.google.com/apis/docs/getting-started).

```bash
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
```

This `$PROJECT_ID` will be used in the .env.json file in `project_id`.

## Setting up Tailscale
We will use Tailscale to provide a cross-region network (instead of creating bridge networks between many VPCs). Doing so is very straightforward.

First, create a Tailscale account. [https://login.tailscale.com/start](https://login.tailscale.com/start)

Then go to the admin console and create a new auth key. [https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys). 

Your key should look like this image:

![Tailscale Auth Key](/case-studies/duckdb-log-processing/images/Tailscale-Auth-Key.png)

When you are done, you should get a key like: `tskey-auth-kFGiAS7CNTRL-2dpMswsLF8UdDydPRMiWDUEXAMPLE`.

This key will be used in the .env.json file in `tailscale_key`.

## Terraform Setup
Now we are ready to use Terraform. First install Terraform - [https://learn.hashicorp.com/tutorials/terraform/install-cli](https://learn.hashicorp.com/tutorials/terraform/install-cli).

Then, initialize Terraform. This will download the plugins needed to run the script.
```bash
cd terraform
terraform init
```

Then, run the script to plan the infrastructure.
```bash
terraform plan -out plan.out
```

This will show you what resources will be created. If you are happy with the plan, you can apply it.
```bash
terraform apply plan.out
```

Once that is completed, you will have a set of nodes that can communicate with each other. To destroy the infrastructure, run:
```bash
terraform destroy -plan=plan.out
```

## Installing Bacalhau locally
Installing the Bacalhau client is very straightforward. Simply type the following:
```bash
curl -sL https://get.bacalhau.org/install.sh | bash
```

This will install the Bacalhau client. Additionally, you will have to set up your environment variables for communicating with the cluster - these will be in the `bacalhau.run` file in your `terraform` directory. They should look something like this:
```bash
export BACALHAU_IPFS_SWARM_ADDRESSES=/ip4/100.118.19.12/tcp/46883/p2p/QmeGoAkQEKedJK5mKNHbNTibdSUwLetKEXAMPLE
export BACALHAU_API_HOST=0.0.0.0
export BACALHAU_API_PORT=1234
export BACALHAU_PEER_CONNECT=/ip4/100.116.19.97/tcp/37063/p2p/Qma5AkfRfaYZ4Ewv2BLYXLTwGKYS2nsWEXAMPLE
```

You will have to update the `BACALHAU_API_HOST` with the value of the IP address from the `BACALHAU_IPFS_SWARM_ADDRESSES`. So you should execute the following command:

```bash
# Put the value 100.118.19.12 into BACALHAU_API_HOST
export BACALHAU_API_HOST=$(echo $BACALHAU_IPFS_SWARM_ADDRESSES | sed -n -e 's/^.*\/ip4\/\([^\/]*\)\/.*$/\1/p')
```

## Running the Job
To run the job, you can reuse the `job.yaml` file in this directory. To do so, simply type:

`cat job.yaml | bacalhau create`

This will reach out to the network and run the job. If you would like to do this manually on the command line, the command is the following:
```bash
bacalhau docker run \
  -i file:///db:/db \
  -i file:///var/log/logs_to_process:/var/log/logs_to_process \
  --network=full \
  -s zone=europe-west4-b \
  docker.io/bacalhauproject/motherduck-log-processor:1.0.2 \
  -- /bin/bash -c "python3 /process.py /var/log/logs_to_process/aperitivo_logs.log.1 \"SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY '@timestamp'\""
```

This will run the job on the cluster. You can see the results by typing:
```bash
bacalhau describe <JOBID> # This will be output by the previous command
```

Finally, if you would like to run the job on every node in the cluster, you can do so by typing:
```bash
cat job_multizone.yaml | bacalhau create
```

To do the same from the command line is nearly the same:
```bash
bacalhau docker run \
  -i file:///db:/db \
  -i file:///var/log/logs_to_process:/var/log/logs_to_process \
  --network=full \
  --concurrency 16 \
  docker.io/bacalhauproject/motherduck-log-processor:1.0.2 -- \
  /bin/bash -c "python3 /process.py /var/log/logs_to_process/aperitivo_logs.log.1 \"SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY '@timestamp'\""
```