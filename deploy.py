import subprocess
import argparse
import uuid

def deploy_bicep_template(template_file, parameters):
    command = [
        "az", "deployment", "group", "create",
        "--resource-group", parameters['resource_group'],
        "--template-file", template_file,
        "--parameters", f"uniqueId={parameters['unique_id']}",
        f"location={parameters['location']}"
    ]
    subprocess.run(command, check=True)

def destroy_bicep_template(resource_group, unique_id):
    command = [
        "az", "group", "delete",
        "--name", resource_group,
        "--yes", "--no-wait"
    ]
    subprocess.run(command, check=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy or destroy Azure resources using Bicep templates.")
    parser.add_argument('--create', action='store_true', help="Create resources")
    parser.add_argument('--destroy', action='store_true', help="Destroy resources")
    args = parser.parse_args()

    unique_id = str(uuid.uuid4())
    resource_group = f"rg-{unique_id}"

    if args.create:
        # Create resource group
        subprocess.run(["az", "group", "create", "--name", resource_group, "--location", "eastus"], check=True)

        # Deploy control plane
        deploy_bicep_template("control_plane.bicep", {"resource_group": resource_group, "unique_id": unique_id, "location": "eastus"})

        # Deploy support nodes
        deploy_bicep_template("support_nodes.bicep", {"resource_group": resource_group, "unique_id": unique_id, "location": "westus"})
        deploy_bicep_template("support_nodes.bicep", {"resource_group": resource_group, "unique_id": unique_id, "location": "centralus"})
        deploy_bicep_template("support_nodes.bicep", {"resource_group": resource_group, "unique_id": unique_id, "location": "eastus2"})

    if args.destroy:
        destroy_bicep_template(resource_group, unique_id)
