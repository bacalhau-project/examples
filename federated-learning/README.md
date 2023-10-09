# Multi-Region Federated Learning with Bacalhau and Tailscale on AWS

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

Copy the auth key to the install_tailscale.sh.example script and rename it to install_tailscale.sh

Follow instuctions and run cells in this [notebook](./run.ipynb) or copy and run the instructions below

## Installing Dependencies

### 1. Terraform

To install Terraform, follow the [official guide](https://learn.hashicorp.com/tutorials/terraform/install-cli) from HashiCorp.

### 2. Python3

The installation of Python 3 depends on your operating system. Here are some common methods:

- macOS: `brew install python3`
- Ubuntu: `sudo apt-get install python3`

Or you can download it from the [official website](https://www.python.org/downloads/).

### 3. AWS CLI

To install the AWS CLI and configure it:

1. [Install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html).
2. Once installed, run `aws configure` to set up your credentials.

### 4. Bacalhau CLI

1. [Install the Bacalhau CLI](https://docs.bacalhau.org/getting-started/installation).

## Add your regions to regions.md
### Note: The Bootstrap region should be first

### To Get AMI IDs for each region (Only if you want to use different AMI)
```
python3 get_instance_amis.py --name "Deep Learning AMI GPU PyTorch 2.0.1 (Ubuntu 20.04) 20230620"
```
#### In this file `./tf/.env.example` Replace the Values of "locations" with the values outputted from the above command. Replace The values of the keys with your own key values and also the value of instance_type if you want and copy it to `.env.json`
```
cp -r .env.example .env.json
```
### Deploying the infra
```
./bulk-deploy.sh create
```
#### Building the container (Optional)

##### Install Git-LFS
```
sudo apt-get install git-lfs
git lfs install
```

##### Clone the repo and follow the instructions in this [readme](https://huggingface.co/VedantPadwal/federated/blob/main/README) to build your container
```
git clone https://huggingface.co/expanso/federated/
```

### Running the jobs

After successfully completing the Terraform deployment, ensure you've set up the necessary environment variables. Execute the following command in your terminal:

```
source tf/aws/baclhau.run
REGION=$(awk '!/^#/' regions.md | head -n 1)
export BACALHAU_NODE_CLIENTAPI_HOST=$(jq -r '.outputs.ip_address.value' "./tf/aws/terraform.tfstate.d/${REGION}/terraform.tfstate")
```

### Job0: Gradient Generation

**Objective:** Generate gradients from local private data on the nodes and upload them to an S3 bucket.

**Execution Command:**

```bash
python3 generate_gradients.py
```

**Details:** 
- The script determines the region names from `./tf/.env.json`.
- For each region and unique bucket name (since bucket names must be unique), the script performs the following operations:
  1. Mounts training images located at `/images` on the node.
  2. Fine-tunes the global model.
  3. Saves the resulting gradients to the specified S3 bucket.

### Job1: Model Update with Gradients

**Objective:** Merge outputs from all S3 buckets into a single bucket. Then, execute the job on a node located in the same region as this bucket, and save the updated model within this bucket.

```bash
python3 update_model.py
```
