## To authenticate with Azure and create spot VMs using a script, you need credentials.

### **Step 1: Install Azure CLI (if not already installed)**
If you haven’t installed the Azure CLI, download and install it from:
[https://learn.microsoft.com/en-us/cli/azure/install-azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

### **Step 2: Login to Azure**
Run the following command in a terminal:
```sh
az login
```
This will open a browser for authentication. If you are using a headless machine, use:
```sh
az login --use-device-code
```

## Config

Just create SSH key, use your bacalhau orchestrator url and token.

### image
Use auto for Canonical:ubuntu-24_04-lts:server:latest or chose your own.

> **Note:** Startup scripts are prepared for Ubuntu/Debian distros and will not work for other.

To list available images:
```bash
az vm image list --output table
```

### machine_type
Choose machine type that likely will be available as target for Spot VMs

To list machine types in certain region
```bash
az vm list-sizes --location eastus
```

### node_count
Use auto for even spread of VMs across regions or us int to set how many machines should be spawned in certain region.

> **Note:** Total number of nodes will not be bigger than max_instances setting.


## Usage

Running deploy_spot.py requires config.yaml file and created SSH keys.

It is best to create virtual env and install dependencies in it. 
```bash
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt

python deploy_spot.py --action [ list | create | destroy ]
```