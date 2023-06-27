# Instructions to Build From Scratch

## Introduction
This file is for building the entire system from scratch. It will go through the steps of setting up Google Cloud, Tailscale, and then running the terraform script to create the cluster.

If you would just like to run the job, and not build from scratch, please see the [README.md](../README.md) file.

## Architecture
This sample example consists of three components:
* A container that runs a python script that generates logs
* A container that runs a python script that processes logs and uploads them to a cloud storage bucket
* A terraform script that provisions a cluster of 16 nodes on Google Cloud

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

During this process, it will do a series of tasks:
* Create a service account for the nodes to use to access the buckets in the project
* Use the `terraform/cloud-init/init-vm.yml` to initialize the node. On each node, in order, this will:
  * Move the files from `terraform/node_files` to the node in the directory `/node`. These files include:
    * log_generator.py - a script that generates mock logs
    * /etc/logrotate.d/{app_name} - a logrotate script that rotates the logs which takes the `app_name` from .env.json
    * /etc/systemd/system/log-generator.service - a systemd service that runs the log_generator.py script which takes the `app_name` from .env.json. It writes all logs to `{ logs_dir }` which is hard coded in main.tf (to /var/log/). `log_dir` is set in `main.tf`
    * 
    * Install a logrotate script in `/etc/cron.hourly` to rotate the logs hourly. It picks up the configuration for this in `/etc/logrotate.conf` (which automatically picks up all the config from `/etc/logrotate.d/`.
    * Installs `/node/start-bacalhau.sh` script. Inside this script, it:
      * Sets the `CONNECT_PEER` to "none"
      * Then pulls the `TAILSCALE_ADDRESS` (if any) and sets that as the preferred address.
      * If the `/etc/bacalhau-bootstrap` file is present, then it uses that as the environment variables. This will be installed on all worker nodes, but not the bootstrap node.
      * Starts Bacalhau
    * Installs `/etc/systemd/system/bacalhau.service` which runs the `/node/start-bacalhau.sh` script, from `/node`.  
  * Copy the local ssh keys to the server to authorized_keys. This allows you to ssh into the server.
  * Create the `/node` and `/data` directories.
  * Install tailscale and add the node to the network (using the `tailscale_key` from .env.json). It also sets a `node_name` based on the `app_name` from .env.json and the region.
  * Install docker
  * Install Bacalhau. Currently it does it from a named build (because of some changes not yet in main), but soon it will do it from production.
  * Creates the `{logs_dir}` directory and the `{logs_to_process` directory. The latter is hard coded (because of the way we install everything, we could not use a variable here).
  * Install a virtual environment in `/node/log_generator_env` and install the python dependencies `faker`. This is required for the `log_generator.py` script.
  * Download the list of alphabetical clean words from a public bucket. This should probably be in a github repo.
  * Expand the memory for `net.core.rmem_max` (needed for IPFS & libp2p)
  * Restart all the services.
* Create a VM - it will do so in each `location` from the `.env.json` file.
* Create a storage bucket. This will be named `'project_id'-'zone'-archive-bucket`.
* IF BOOTSTRAP NODE:
  * Wait for bacalhau to start
  * Then copy the bootstrap information to local (`bacalhau.run`)
* IF WORKER NODE:
  * Copy `bacalhau.run` to the node in `/etc/bacalhau-bootstrap`
  * Run bacalhau with the bootstrap information.
* In all cases, the Tailscale address (rather than private IP) is used, if available.

Once that is completed, you will have four nodes that can communicate with each other. To destroy the infrastructure, run:
```bash
terraform destroy -plan=plan.out
```

## Building the job
Once the nodes have been provisioned, they will begin producing the logs into the { log_dir }. It will take one hour to rotate the logs into the /var/log/logs_to_process directory. Once that is done, you will be able to run the log processing bacalhau job using Bacalhau.

The job container is in the job-container directory. To build it, run:
```bash
# Use a container registry that you have access to
$CONTAINER_ORG=bacalhauproject
$CONTAINER_NAME=motherduck-log-processor
$VERSION=v1.0
docker buildx build --push --platform linux/amd64,linux/arm/v7,linux/arm64/v8 -t "docker.io/$CONTAINER_ORG/$CONTAINER_NAME:$VERSION" .
```

Inside the container there is a file called `process.py`. This is the script that will be run by Bacalhau. It takes the following arguments:
* `log-dir` - the directory where the logs are located. This is the directory that is rotated into every hour. It is hard coded in `main.tf` to `/var/log/logs_to_process`.
* `bucket-name` - the label of the bucket to upload the processed logs to. It will prepend by the project_id and zone so it will upload to `{project_id}-{zone}-{label}`. This bucket must already exist.
* `query` - the query, in quotes, that will be executed over the log.

A sample execution - if you need to test locally - will look like this:
```bash
$VERSION=v1.0
$CONTAINER_ORG=bacalhauproject
$CONTAINER_NAME=motherduck-log-processor
$LOCAL_DIR_TO_MOUNT=/var/log/logs_to_process
$APPNAME=aperitivo
$QUERY="SELECT * FROM logs WHERE log_level = 'ERROR'"
# Example:
docker run --rm -v $LOCAL_DIR_TO_MOUNT:/var/log/logs_to_process docker.io/$CONTAINER_ORG/$CONTAINER_NAME:$VERSION /var/log/logs_to_process/$APPNAME.log.1 $QUERY

# After variable substitution, it would look like this:
docker run --rm -v /var/log/logs_to_process:/var/log/logs_to_process docker.io/bacalhauproject/duckdb-log-processor:v1.0 /var/log/logs_to_process/aperitivo.log.1  "SELECT * FROM logs WHERE log_level = 'ERROR'"
```

The job also supports gzip expansion, if necessary.

To actually build the job into a new container, execute the following:
```bash
docker buildx build --push --platform linux/amd64,linux/arm/v7,linux/arm64/v8 -t docker.io/$CONTAINER_ORG/$CONTAINER_NAME:$VERSION .`
```

You must have push access to the organization and repository. If you are using docker.io, you will need to log in first.

## Running the Job
To run the job, go to the [regular instructions](README.md)