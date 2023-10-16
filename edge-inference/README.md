# Bacalhau Multi-Region Edge-Inference with Tailscale

## Overview
In this example we will simulate running object detection on the data stored on two edge bacalhau nodes located in two different AWS regions.

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

## Writting the Python Inference Script (Optional)

For this example we use the jetson emulator SDK
To install the package run
```
 pip install jetson-emulator
```

In this script we will use the googlenet model to run inference on sample images
```python
import jetson_emulator.inference as inference
import jetson_emulator.utils as utils

# load the recognition network
net = inference.imageNet("googlenet")
for x in range(1,6):
	# emulator API to generate sample images for imageNet
	filename = net.emulatorGetImageFile()      
	img = utils.loadImage(filename) 
	class_idx, confidence = net.Classify(img)            
	class_desc = net.GetClassDesc(class_idx)            
	print("image "+str(x)+" is recognized as '{:s}' (class #{:d}) with {:f}% confidence".
	format(class_desc, class_idx, confidence*100))
```

#### Building the container (Optional)

You can use a base image of our choice and install the dependencies we need
In this case we will use the balenalib/jetson-tx2-ubuntu-python for simulating a Jetson-TX2 device 
```Dockerfile
FROM balenalib/jetson-tx2-ubuntu-python

RUN pip install jetson-emulator
```

To Build and Push the container run this command
```
 sudo docker buildx build --push --platform linux/amd64,linux/arm64,linux/arm/v7 -t expanso/jetson .
```

### Deploying the infra

```
./bulk-deploy.sh create
```
### Running the job

After successfully completing the Terraform deployment, ensure you've set up the necessary environment variables. Execute the following command in your terminal:

```
cd tf/aws/ && source baclhau.run
REGION=$(awk '!/^#/' regions.md | head -n 1)
export BACALHAU_NODE_CLIENTAPI_HOST=$(jq -r '.outputs.ip_address.value' "./tf/aws/terraform.tfstate.d/${REGION}/terraform.tfstate")
```

### Running the job across all the nodes
```
bacalhau docker run --target=all -i https://raw.githubusercontent.com/bacalhau-project/example-scripts/main/edge-inference/script.py expanso/jetson -- python inputs/script.py
```

### Viewing the Output Logs of the Job

```
bacalhau get <YOUR-JOB-ID>
```