# Running Multi-SQLite Bacalhau Nodes 

## Overview
SQLite is one of the most popular databases in the world, but it, traditionally, runs in process, meaning it isn't available to other processes or nodes. This is a problem, as the data is only available on a single node, making it difficult to port intelligence to other machines or centralize information.

Bacalhau solves this problem by mounting the SQLite file in a container and running a query against it. This allows you to run a query against a SQLite file on a single node or every node in the network.

## Prerequisites for This Example
* Azure account (if you do not have a Bacalhau cluster already running)
* Tailscale account

## Setting up your Tailscale account
We will use Tailscale to have all the nodes in the network be able to communicate with each other. If you have already set up a Bacalhau cluster, you can skip this step. Additionally, if you have a different way of connecting the nodes, you can skip this step.

## Create and Configure Your Tailscale Account
We will use Tailscale to provide a cross-region network (instead of creating bridge networks between many VPCs). Doing so is very straightforward.

First, create a Tailscale account. [https://login.tailscale.com/start](https://login.tailscale.com/start)

Then go to the admin console and create a new auth key. [https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys). 

Your key should look like this image:

![Tailscale Auth Key](/case-studies/duckdb-log-processing/images/Tailscale-Auth-Key.png)

When you are done, you should get a key like: `tskey-auth-kFGiAS7CNTRL-2dpMswsLF8UdDydPRMiWDUEXAMPLE`.

This key will be used in the .env.json file in `tailscale_key`.

## Configuring Your 
Now we will create Azure credentials to use on each machine. Get the Azure client_id, client_secret, and tenant_id from the Azure CLI. First, we will log in and get the subscription ID.
```bash
az login
az account show
export SUBSCRIPTION_ID=$(az account list --query "[?isDefault].id" -o tsv)
```
Next we will create a service principal for use with Terraform.
```bash
az ad sp create-for-rbac --name "bacalhau-multi-region-example" --role contributor --scopes /subscriptions/$SUBSCRIPTION_ID --sdk-auth
```

This will output something like this:
```json
{
  "clientId": "1df9e26b-9ef5-4646-b4f0-EXAMPLE",
  "clientSecret": "h6~8Q~gcAWMn7-vl_NCbqmUi1.JLQ_NEXAMPLE",
  "subscriptionId": "72ac7288-fb92-4ad6-83bc-5cEXAMPLE",
  "tenantId": "21e3ecc7-6fb3-47f8-bc36-f645EXAMPLE",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

Paste the contents of this block in your .env.json file.

Build command for jobcontainer:
```bash
docker buildx build --platform linux/amd64,linux/arm64 --push -t bacalhauproject/query-sqlite:0.0.1 .
```

Display all resource groups created:
```bash
az group list --query "[?starts_with(name, 'multisqlite')].{name: name, location: location}"
```

Display the vm in a single resource group:
```bash
./display_vm_details.sh multisqlite-bacalhau-koreasouth-rg
```

List the file on a VM:
```bash
ssh daaronch@20.200.169.13 'sudo ls /db'
```

Run docker on a single VM in the Bacalhau network:
```bash
bacalhau docker run -s region=francecentral ubuntu echo "hello francecentral"
```

Run docker on every node in the Bacalhau network:
```bash
bacalhau docker run --concurrency=36 ubuntu echo "hello everybody"
```

Look at the outputs of the job:
```bash
bacalhau describe <JOBID>
```

Show it having executed 36 times:
```bash
bacalhau describe <JOB> | grep "JobID" | wc -l
```

Get columns of a SQLite table:
```bash
bacalhau docker run -i file:///db:/db docker.io/bacalhauproject/query-sqlite:0.0.1 -- /bin/bash -c "python3 /query.py 'PRAGMA table_info(sensor_data);'"
```

Show the output:
```bash
bacalhau describe <JOBID>
```

Query all the rows from a single instance:
```bash
cat job.yaml | bacalhau create
```

Get the results:
```bash
bacalhau get <JOBID>
```

Query all the rows from every instance and return just the lat/long where the humity is above 93 using SQLite:
```bash
cat job.yaml | bacalhau create
```

SQLite query to return values where the column 'humidity' is greater than 93:
```bash
SELECT * FROM sensor_data WHERE humidity > 93;
```