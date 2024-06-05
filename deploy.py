import subprocess

def deploy_bicep_template(template_file, parameters_file):
    command = [
        "az", "deployment", "group", "create",
        "--resource-group", "myResourceGroup",
        "--template-file", template_file,
        "--parameters", parameters_file
    ]
    subprocess.run(command, check=True)

if __name__ == "__main__":
    deploy_bicep_template("control_plane.bicep", "control_plane_parameters.json")
    deploy_bicep_template("support_nodes.bicep", "support_nodes_parameters.json")
