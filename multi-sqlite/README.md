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