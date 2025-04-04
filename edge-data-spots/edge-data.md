
# Edge Data Deployment – Beginner Guide

## 1. Prerequisites – Required Tools

Make sure your system has the following installed:

- Python 3.10 or higher
- python3-pip
- `uv` (install via `pip install uv`)
- `aws-cli` – [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)

---

## 2. Configure AWS CLI

Run the following command:

`aws configure`

## 3. Navigate to the project directory

Run:

`uv run -s util/get_ubuntu_amis.py`

Choose the desired AMI ID from the `ubuntu_amis` output (all are ARM-based) and update your `config.yaml`:

```yaml
machine_type: <chosen_machine_type>
```

## 5. Update config.yaml
Fill in the following fields:
```yaml
orchestrators:
- nats://:4222
public_ssh_key_path:

token: ""


```

## 6. Deploy EFS and Spot Instances
Run the deployment script:

`uv run -s ./deploy_spot.py create`

Check if instances have registered correctly on demo machine:

`bacalhau node list`


## 7. Verify NFS mount on a node
SSH into one of the Spot instances and run:

`df -h`

Confirm `/mnt/data` is mounted properly.

## 8. Generate test data
Run the test job to generate random files:


`bacalhau job submit generate.yaml`

## 9. Run the metadata generation job
Submit the main processing job:

`bacalhau job submit create_metadata.yaml`