# Bacalhau Multi-Region GCP Cluster Setup

This Terraform configuration sets up a Bacalhau cluster across multiple Google Cloud Platform (GCP) regions. The cluster consists of:

- Multiple compute nodes across specified GCP regions
- Each node runs Bacalhau in a Docker container
- Automatic health checks and monitoring

The cluster is configured through the `env.json`.

## Key Components

### Configuration Files

- `cloud-init/init-vm.yml`: Cloud-init configuration that sets up the VM environment, installs required packages, configures systemd services, and deploys Bacalhau configuration files.
- `config/docker-compose.yml`: Docker Compose configuration that runs Bacalhau in a privileged container, mounts necessary volumes, configures health checks, and ensures container restart on failure.
- `scripts/bacalhau-startup.service`: Systemd service that runs after Docker is available
- `scripts/startup.sh`: Bash script for running by systemd that detects cloud provider metadata, configures node information, starts Docker Compose services, verifies container health, and handles error conditions.

The VAST majority of the configuration is done through the `env.json` file - though lots more configuration is possible!

## Configuration Variables

Here's what each variable in `env.json` controls:

- `bootstrap_project_id`: Existing GCP project ID used to create the new project and grant permissions. It will only be used to create the new project.
- `base_project_name`: Base name for the new GCP project (will have timestamp appended)
- `gcp_billing_account_id`: Your GCP billing account ID for project charges. Get it with:
  ```bash
  gcloud beta billing accounts list --format="value(name)"
  ```
- `gcp_user_email`: Email of the GCP user to grant owner permissions. Get it with:
  ```bash
  gcloud config get-value account
  ```
- `org_id`: Your GCP organization ID. Get it with:
  ```bash
  gcloud organizations list --format="value(name)"
  ```
- `app_tag`: Custom tag for identifying resources (e.g., "bacalhau-demo-cluster")
- `bacalhau_data_dir`: Directory path for Bacalhau job data storage
- `bacalhau_node_dir`: Directory path for Bacalhau node configuration
- `username`: SSH username for accessing the compute nodes
- `public_key`: Path to your public SSH key for node access
- `locations`: Map of regions and their configuration:
  - `zone`: GCP zone within the region
  - `node_count`: Number of nodes to create in this region
  - `machine_type`: GCP machine type for the nodes (e.g., "e2-standard-4")

## Prerequisites

- Terraform >= 1.0.0
- Google Cloud SDK installed and configured
- GCP billing account enabled
- Organization ID available
- SSH key pair for instance access

## Quick Start

1. Copy the example environment file:
```bash
cp env.json.example env.json
```

1. Edit `env.json` with your GCP details.


2. Initialize Terraform:
```bash
terraform init
```

1. Apply the configuration:
```bash
terraform apply
```

## Verifying Cluster Health

After deployment, you can verify the health of your Bacalhau nodes:

1. Get the instance IPs:
```bash
terraform output instance_ips
```

2. SSH into a node:
```bash
ssh -i ~/.ssh/id_rsa ubuntu@<public-ip>
```

3. Check Docker container status:
```bash
docker ps
```

4. Verify Bacalhau node health:
```bash
curl localhost:1234
```

## Running Your First Job

Once the cluster is healthy, you can submit jobs:

1. Install Bacalhau CLI:
```bash
curl -sL https://get.bacalhau.org/install.sh | bash
```

2. Submit a test job:
```bash
bacalhau docker run ubuntu echo "Hello from Bacalhau!"
```

3. List jobs:
```bash
bacalhau list
```

4. Get job results:
```bash
bacalhau get <job-id>
```

## Configuration Details

### Key Files

- `main.tf`: Main Terraform configuration
- `variables.tf`: Input variables for the deployment
- `outputs.tf`: Output values from the deployment
- `config/config.yaml`: Bacalhau node configuration
- `config/docker-compose.yml`: Docker Compose setup
- `scripts/startup.sh`: Node initialization script
- `scripts/bacalhau-startup.service`: Systemd service file

### Customization Options

- Add more regions in `env.json` under `locations`
- Change machine types for different performance needs
- Modify Bacalhau configuration in `config/config.yaml`
- Adjust Docker Compose settings in `config/docker-compose.yml`

## Cleanup

To destroy the cluster and associated resources:
```bash
terraform destroy
```

## Troubleshooting

1. **Deployment Fails**
   - Verify GCP permissions
   - Check billing account status
   - Ensure APIs are enabled in GCP console

2. **Nodes Not Healthy**
   - Check system logs: `journalctl -u bacalhau-startup.service`
   - Verify Docker logs: `docker logs <container-id>`
   - Ensure ports 1234 and 4222 are open

3. **Jobs Not Running**
   - Verify NATS connection in config
   - Check node registration status
   - Ensure compute is enabled in config

## Support

For additional help, please refer to the official Bacalhau documentation or open an issue in the repository.
