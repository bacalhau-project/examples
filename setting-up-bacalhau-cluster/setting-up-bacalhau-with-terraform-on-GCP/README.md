# Bacalhau Multi-Region GCP Cluster Setup

This Terraform configuration sets up a Bacalhau cluster across multiple Google Cloud Platform (GCP) regions. The cluster consists of:

- Multiple compute nodes across specified GCP regions
- Each node runs Bacalhau in a Docker container
- Automatic health checks and monitoring
- Secure communication between nodes
- Persistent storage for job data

The cluster is configured through the `env.json` file which specifies:
- GCP project and billing details
- Machine types and zones for each region
- SSH access configuration
- Bacalhau data and node directories

## Key Components

### Configuration Files

- `cloud-init/init-vm.yml`: Cloud-init configuration that:
  - Sets up the VM environment
  - Installs required packages (Docker, Docker Compose)
  - Configures systemd services
  - Deploys Bacalhau configuration files

- `config/docker-compose.yml`: Docker Compose configuration that:
  - Runs Bacalhau in a privileged container
  - Mounts necessary volumes
  - Configures health checks
  - Ensures container restart on failure

- `scripts/bacalhau-startup.service`: Systemd service that:
  - Runs after Docker is available
  - Executes the startup script
  - Ensures proper service ordering
  - Provides logging through journald

- `scripts/startup.sh`: Bash script that:
  - Detects cloud provider metadata
  - Configures node information
  - Starts Docker Compose services
  - Verifies container health
  - Handles error conditions

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

2. Edit `env.json` with your GCP details:
```json
{
    "base_project_name": "bacalhau-cluster",
    "org_id": "your-org-id",
    "gcp_billing_account_id": "your-billing-account-id",
    "gcp_user_email": "your-email@example.com",
    "locations": {
        "us-central1-a": {
            "machine_type": "e2-medium",
            "zone": "us-central1-a"
        }
    },
    "app_name": "bacalhau",
    "username": "ubuntu",
    "public_key": "~/.ssh/id_rsa.pub",
    "bacalhau_config_file_path": "./config/config.yaml",
    "bacalhau_data_dir": "/var/lib/bacalhau",
    "bacalhau_node_dir": "/var/lib/bacalhau/node"
}
```

3. Initialize Terraform:
```bash
terraform init
```

4. Apply the configuration:
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
