# Multi-SQLite Bacalhau Nodes with Tailscale

## Overview


Create a tailscale account.
Add a tag to your tailscale account - https://login.tailscale.com/admin/acls

```jsonc
// Example/default ACLs for unrestricted connections.
{
	// Declare static groups of users. Use autogroups for all users or users with a specific role.
	// "groups": {
	//  	"group:example": ["alice@example.com", "bob@example.com"],
	// },

	// Define the tags which can be applied to devices and by which users.
	"tagOwners": {
    "tag:bacalhau-multi-region-example": ["autogroup:admin"],
	},

	// Define access control lists for users, groups, autogroups, tags,
	// Tailscale IP addresses, and subnet ranges.
	"acls": [
		// Allow all connections.
		// Comment this section out if you want to define specific restrictions.
		{"action": "accept", "src": ["*"], "dst": ["*:*"]},
	],

	// Define users and devices that can use Tailscale SSH.
	"ssh": [
		// Allow all users to SSH into their own devices in check mode.
		// Comment this section out if you want to define specific restrictions.
		{
			"action": "check",
			"src":    ["autogroup:members"],
			"dst":    ["autogroup:self"],
			"users":  ["autogroup:nonroot", "root"],
		},
	],

	// Test access rules every time they're saved.
	// "tests": [
	//  	{
	//  		"src": "alice@example.com",
	//  		"accept": ["tag:example"],
	//  		"deny": ["100.101.102.103:443"],
	//  	},
	// ],
}
```
Generate a tailscale auth key - https://login.tailscale.com/admin/settings/keys

## Log in to Azure
Get the Azure client_id, client_secret, and tenant_id from the Azure CLI
```bash
az login
az account show
```
## Get your subscription ID with the az tool 
```bash
export SUBSCRIPTION_ID=$(az account list --query "[?isDefault].id" -o tsv)
```
## Create a resource group
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