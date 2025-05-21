# Repository Cleanup Steps

## Files to Keep

These files should be kept as they are essential for job submission and tracking:

1. `README.md` - Updated documentation
2. `CLAUDE.md` - Guidelines for Claude Code
3. `bacalhau_job_submitter.py` - Core job submission script with UI
4. `job_status_checker.py` - Script for checking job status
5. `run_jobs.sh` - Simple shell script for job submission
6. `job.yaml` - Default job specification
7. `stress_job.yaml` - Stress test job specification
8. `list_all_jobs_by_state_and_node.py` - Utility for listing jobs by state
9. `requirements.txt` - Simplified dependencies file

## Files/Directories to Remove

These files and directories should be removed as they relate to infrastructure provisioning and deployment:

1. `control_plane.bicep` - Azure infrastructure template
2. `deploy_bacalhau.py` - Script for deploying Bacalhau
3. `deploy_resources.py` - Script for managing Azure resources
4. `deploy_spot.py` - Script for managing AWS spot instances
5. `list_ips.py` - Script for listing Azure VM IPs
6. `support_nodes.bicep` - Azure infrastructure template
7. `spot_instance_template.json` - AWS template
8. `get_ubuntu_amis.py` - Script for finding Ubuntu AMIs
9. `agent-container/` - Directory with Bacalhau agent installation
10. `spot_creation_scripts/` - Directory with AWS scripts
11. `remote/` - Directory with remote execution scripts
12. `remote_logs/` - Directory for logs
13. `helix_job.yml` - Infrastructure job definition
14. `install-helix.sh` - Helix installation script
15. `itermocil.window-layout` - Development environment config
16. `MACHINES.json` - Machine configuration
17. `UNIQUEID` - Deployment identifier
18. `app.yml` - Application configuration
19. `all_images.txt` - List of container images
20. `all_images_online.txt` - List of online container images
21. `david-aws-keypair.pem` - AWS key pair
22. `job/` - Directory for job outputs

## Cleanup Command

To execute the cleanup, run the following bash command in the repository root:

```bash
# Keep essential files
mkdir -p /tmp/bacalhau-queue-keep
cp README.md CLAUDE.md bacalhau_job_submitter.py job_status_checker.py run_jobs.sh job.yaml \
   stress_job.yaml list_all_jobs_by_state_and_node.py requirements.txt /tmp/bacalhau-queue-keep/

# Remove all other files
rm -rf *

# Restore kept files
cp /tmp/bacalhau-queue-keep/* .
rm -rf /tmp/bacalhau-queue-keep
```

## Note on Requirements

The `requirements.txt` file has been simplified to include only dependencies needed for job submission and tracking:

- rich - For terminal UI components
- asyncio - For async operations
- pandas - For data processing
- tqdm - For progress bars
- prettytable - For tabular display
- pygments - For syntax highlighting
- pyyaml - For YAML parsing
- nest-asyncio - For nested async operations