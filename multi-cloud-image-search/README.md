# Deploying Multi-Cloud-Image-Search Bacalhau Nodes with Tailscale

## Overview
In this guide, we will deploy Bacalhau nodes on both AWS and GCP, and demonstrate how to run jobs across multiple clouds simultaneously.


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

Copy the auth key to the install_tailscale.sh.example script and rename it to install_tailscale.sh

Now just run "./bulk-deploy.sh". This will create/switch to a terraform workspace for every zone in the zone.txt file.

After successfully completing the Terraform deployment, execute the following commands in your terminal to set up the environment variables:

```
cd tf/aws/ && source bacalhau.run
export BACALHAU_NODE_CLIENTAPI_HOST=$(jq -r '.outputs.ip_address.value' terraform.tfstate.d/ca-central-1/terraform.tfstate)
```

To test the network, run a simple job across all nodes using the following command:

```
bacalhau docker run \
--target=all \
--gpu 1 \
expanso/sam:new \
-i file:///home/ubuntu/sea_creatures:/inputs \
-- /bin/bash -c 'python /sam.py --input /inputs --output /outputs --prompt "fish"'
```
