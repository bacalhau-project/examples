# Instructions to Build From Scratch

## Architecture
This sample example consists of three components:
* A container that runs a python script that generates logs
* A container that runs a python script that processes logs and uploads them to a cloud storage bucket
* A terraform script that provisions a cluster of 4 nodes on Google Cloud

You will also have to login with credentials for Google Cloud, and Tailscale.

## Setting up your .env.json file.
In the `terraform` directory, there is a file called `.env.json.example`. Copy this file to `.env.json` and fill in the values. The explanation for all the values are as follows:
* project_id - GCP project ID for the project
* bootstrap_zone: Zone where the bootstrap node for the network will be created
* locations - a set of objects that define the locations of the nodes in the cluster. Each object has the following fields:
  * key - the name of the zone
  * zone - the name of the zone (should be the same as the key)
  * machine_type - the machine type for the node - must be available in that zone
  * storage_location - the location of the storage bucket for the node
  * iam_access - whether to give the node IAM access to the project
  * create_bucket - whether to create a storage bucket for the node
* tailscale_key: An auth key from Tailscale. You can get one from [https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys). It should be "Reusable", "Expiration of 90 days", "Ephemeral" and have a tag of something meaningful to you.
* app_name: A meaningful & unique name - will be used as a prefix on the logs.
* bacalhau_run_file: When Bacalhau starts on the bootstrap node, it creates a `bacalhau.run` file. This file contains the information needed to connect to the cluster. This field specifies the name (but not location) of that file. It will be created in the `/run` directory (unless the installer does not have permissions). During the installation, the file will be copied to the `terraform` directory for installation in non-bacalhau nodes.
* username: The username to use for the nodes - will be added to `sudoers` and be the account needed to ssh into the nodes (should not be necessary).
* public_key: Location of the public key for the account for logging in (e.g. ~/.ssh/id_rsa.pub)
* private_key: Location of the private key for the account for logging in (e.g. ~/.ssh/id_rsa)
* app_tag:  This will be used to group manage the resources created by this script (e.g. delete them all at once)

We will go through filling out all these details shortly.

## Setting up Google Cloud
First, you need to install the Google Cloud SDK. Depending on your platform, you will need to install from a package manager, or directly compile. Instructions to do so are here. [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

After installing, you need to login to your Google Cloud account. [Full Instructions](https://cloud.google.com/sdk/docs/initializing). For most platforms, you should simply type:
```bash
gcloud auth login
```

After logging in, you need to create a project. [Full Instructions](https://cloud.google.com/resource-manager/docs/creating-managing-projects).

```bash
$PROJECT_ID = "my-project"
gcloud projects create $PROJECT_ID
```

You also need to get your billing account ID. 

```bash
gcloud beta billing accounts list
$BILLING_ACCOUNT_ID = "my-billing-account"
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

![Tailscale Auth Key](images/../Tailscale-Auth-Key.png)

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
* It will create a service account for the nodes to use to access the buckets in the project
* It will use the `terraform/cloud-init/init-vm.yml` to initialize the node. On each node, in order, this will:
  * Move the files from `terraform/node_files` to the node in the directory `/node`. These files include:
    * log_generator.py - a script that generates mock logs
    * /etc/logrotate.d/{app_name} - a logrotate script that rotates the logs which takes the `app_name` from .env.json
    * /etc/systemd/system/log-generator.service - a systemd service that runs the log_generator.py script which takes the `app_name` from .env.json. It writes all logs to `{ logs_dir }` which is hard coded in main.tf (to /var/log/). `log_dir` is set in `main.tf`
    * 


# Install terraform
- Download the latest version of terraform from [https://www.terraform.io/downloads.html](https://www.terraform.io/downloads.html)
- Unzip the file and move the binary to a folder in your path (e.g. /usr/local/bin)
- Run `terraform --version` to make sure it is installed correctly
- Run `terraform init` to initialize terraform
- Run `terraform plan` to make sure everything is working correctly
- Run `terraform apply` to provision the infrastructure
- Run `terraform destroy` to destroy the infrastructure
- Run `terraform apply -auto-approve` to provision the infrastructure without prompting for confirmation
- Run `terraform destroy -auto-approve` to destroy the infrastructure without prompting for confirmation
- Run `terraform apply -auto-approve -var="project_id=duckdb-logs-processor"` to provision the infrastructure without prompting for confirmation and with a custom project id


## Building the job
The job for 

- go to job-container
- Build updated container: `docker buildx build --push --no-cache --platform linux/amd64,linux/arm/v7,linux/arm64/v8 --no-cache -t docker.io/bacalhauproject/log-processor:v0.16 .`
  - Make sure to purge previous files for building (can cause key errors): `docker system prune -a`

- Go to `terraform` folder
- Log in to google cloud with `gcloud auth login`
- Make a copy of .env.json.example and rename it to .env.json
- Change the fields to make sense. At a minimum, you will need unique names for:
  - project_id
  - tailscale_key (go here to provision a tailscale_key - https://login.tailscale.com/admin/settings/keys - it should be "Reusable", "Expiration of 90 days", "Ephemeral" and have a tag of something meaningful to you.)
  - app_name
  - username
  - app_tag
- Run `terraform plan -out=tf.out -var-file=.env.json`
- If there are no errors, run `terraform apply tf.out`

You now have 4 a four node cluster.

`bacalhau docker run bacalhauproject/duckdb-log-processor:v1.0`

gcloud storage ls --project bacalhau-duckdb-example
gcloud storage ls gs://bacalhau-duckdb-example-europe-west9-b-archive-bucket/
gs://bacalhau-duckdb-example-europe-west9-b-archive-bucket/aperitivo-europe-west9-b-vm-202305281908.json

/var/log/logs_to_process/aperitivo_logs.log.1 archive-bucket "SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY '@timestamp'"

bacalhau --concurrency=4 --network=full -i file:///var/log/logs_to_process:/var/log/logs_to_process docker run docker.io/bacalhauproject/duckdb-log-processor:v1.0 -- /bin/bash -c "python3 /process.py /var/log/logs_to_process/aperitivo_logs.log archive-bucket \"SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY '@timestamp'\""

docker run -v /var/log/logs_to_process/:/var/log/logs_to_process -ti --entrypoint /bin/bash docker.io/bacalhauproject/duckdb-log-processor:v1.0

-------

Challenges with debugging:
* Hard to shell into a container running on Bacalhau. Basically,
  * First run the python script (and make sure it's running in the right environment). Also, simulate the mount points and data available
  * Then bundle into a docker container - run it again locally, again mimicking the  

-------

- API_HOST doesn't output public IP
- Show everything as a flag during `ps` on the node - could leak
- Have a way to set your Bacalhau CLI client by the target IP - e.g. bacalhau set-target 10.1.1.5
- Don't set API_HOST to 0.0.0.0
- Offer a rally-point as a service?  
-     Status: 'Could not inspect image "bacalhauproject/duckdb-log-processor:v0.17"
      - could be due to repo/image not existing, or registry needing authorization:
      Error response from daemon: manifest unknown: manifest unknown'
     -> Not a "couldn't find node to execute"
- What happens when we have 100 nodes, does every job get 99 rejects? - `describe` is super noisy
- Shouldn't override entrypoint - most jobs require "/bin/bash -c"
- A way to mimic running on the cloud locally - particularly mounting in volumes in the same way
- Demonstrate a way to say "downloading context/container" for a job rather than just "running" 