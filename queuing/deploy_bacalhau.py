import argparse
import asyncio
import json
import logging
import os
import random
import sys

import asyncssh

# Setup basic configuration for logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_ed25519")
BACALHAU_INSTALL_CMD = """
curl -sL 'https://get.bacalhau.org/install.sh?dl=BACA14A0-a5e9-40db-801c-dfaf9af6e05f' -o /tmp/install.sh && \
chmod +x /tmp/install.sh && \
sudo /tmp/install.sh
"""
DOCKER_INSTALL_CMD = """
sudo DEBIAN_FRONTEND=noninteractive apt-get update && \
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl && \
sudo install -m 0755 -d /etc/apt/keyrings && \
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
sudo chmod a+r /etc/apt/keyrings/docker.asc && \
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null && \
sudo DEBIAN_FRONTEND=noninteractive apt-get update && \
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
"""

SYSTEMD_SERVICE = """
[Unit]
Description=Bacalhau Service
After=network.target

[Service]
ExecStart=/usr/local/bin/bacalhau serve {node_type_args}
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""


async def ssh_connect(hostname, username, key_filename):
    logging.debug(f"Connecting to {hostname} as {username}")
    return await asyncssh.connect(
        hostname,
        username=username,
        client_keys=[key_filename],
        known_hosts=None,  # Disable host key verification (use with caution)
    )


async def ssh_exec_command(ssh, command):
    result = await ssh.run(command)
    return result.stdout, result.stderr


async def install_docker(ssh):
    logging.debug("Starting Docker installation")
    _, error = await ssh_exec_command(ssh, DOCKER_INSTALL_CMD)
    if error:
        logging.error(f"Docker installation errors: {error}")
        return False
    logging.info("Docker installation command started successfully.")
    return True


async def install_bacalhau(ssh):
    logging.debug("Starting Bacalhau installation")
    install_cmd = f"nohup {BACALHAU_INSTALL_CMD} > /tmp/bacalhau_install.log 2>&1 &"
    await ssh_exec_command(ssh, install_cmd)
    logging.info("Bacalhau installation command started successfully.")

    for _ in range(10):
        output, error = await ssh_exec_command(ssh, "bacalhau version --output json")
        if "clientVersion" in output and "serverVersion" in output:
            logging.info("Bacalhau installed successfully.")
            return True
        await asyncio.sleep(1)

    logging.error("Bacalhau installation failed after multiple attempts.")
    return False


async def post_install_check(ssh):
    logging.debug("Checking Bacalhau installation")
    result = await ssh.run("bacalhau version --output json")
    output = result.stdout.strip()
    error = result.stderr.strip()
    logging.debug(f"Command output: {output}")
    logging.debug(f"Command error: {error}")

    try:
        version_info = json.loads(output)
        if "clientVersion" in version_info and "serverVersion" in version_info:
            logging.info("Bacalhau installed successfully.")
            return True
    except json.JSONDecodeError:
        logging.error("Failed to parse Bacalhau version output.")
        return False


async def setup_orchestrator_node(ssh):
    logging.debug("Setting up orchestrator node")
    await ssh_exec_command(
        ssh,
        "sudo cp /root/.bacalhau/bacalhau.run /tmp/bacalhau.run && sudo chmod 644 /tmp/bacalhau.run",
    )

    orchestrator_node_type_args = ""
    service_content = SYSTEMD_SERVICE.format(node_type_args=orchestrator_node_type_args)

    # Write to a temporary file
    temp_path = "/tmp/bacalhau.service"

    try:
        sftp = await ssh.start_sftp_client()
        async with sftp.open(temp_path, "w") as service_file:
            await service_file.write(service_content)

        # Move the file to the correct location using sudo
        move_cmd = f"sudo mv {temp_path} /etc/systemd/system/bacalhau.service"
        await ssh_exec_command(ssh, move_cmd)

        await ssh_exec_command(ssh, "sudo systemctl enable bacalhau")
        await ssh_exec_command(ssh, "sudo systemctl start bacalhau")

        # The bacalhau.run file may take a few seconds to create - wait until it's present with a loop, but not more than 10 seconds
        for _ in range(10):
            result = await ssh.run(
                "sudo test -f /root/.bacalhau/bacalhau.run && echo exists"
            )
            if result.stdout.strip() == "exists":
                break
            await asyncio.sleep(1)
        else:
            logging.error("Bacalhau run file not found after 10 seconds.")
            return None

        # ssh into the machine, and with sudo, copy the bacalhau.run file to /tmp
        await ssh_exec_command(
            ssh,
            "sudo cp /root/.bacalhau/bacalhau.run /tmp/bacalhau.run && sudo chmod 644 /tmp/bacalhau.run",
        )

        # Copy the bacalhau.run file locally, and put it in memory
        async with sftp.open("/tmp/bacalhau.run", "r") as f:
            details = await f.read()

    except Exception as e:
        logging.error(f"Failed to set up orchestrator node: {e}")
        return None
    finally:
        if sftp is not None:
            sftp.exit()

    return parse_bacalhau_details(details)


def parse_bacalhau_details(details):
    logging.debug("Parsing Bacalhau details")
    lines = details.splitlines()
    connection_info = {}
    for line in lines:
        if line.startswith("export"):
            key, value = line.replace("export ", "").split("=")
            connection_info[key] = value.strip('"')
    return connection_info


def identify_orchestrator_node(machines) -> (list, list):
    logging.debug("Starting deployment of Bacalhau")
    orchestrator_node = None

    # Check if the orchestrator node is already set
    for machine in machines:
        if machine.get("is_orchestrator_node", False):
            orchestrator_node = machine
            break

    if not orchestrator_node:
        # Designate the orchestrator node
        for machine in machines:
            if machine["ip_addresses"]:
                for ip_address in machine["ip_addresses"]:
                    if "public" in ip_address:
                        orchestrator_node = machine
                        machine["is_orchestrator_node"] = (
                            True  # Mark this machine as the orchestrator node
                        )
                        break
            if orchestrator_node:
                break

        # Update the MACHINES.json file
        with open("MACHINES.json", "w") as f:
            json.dump(machines, f, indent=4)

    if not orchestrator_node:
        logging.error("No suitable orchestrator node found.")
        return

    machines.remove(orchestrator_node)

    return orchestrator_node, machines


async def deploy_bacalhau(orchestrator_node, machines):
    orchestrator_node_public_ip = next(
        (ip["public"] for ip in orchestrator_node["ip_addresses"] if "public" in ip),
        None,
    )
    if not orchestrator_node_public_ip:
        logging.error("No public IP found for the orchestrator node.")
        return

    ssh = await ssh_connect(
        orchestrator_node_public_ip,
        orchestrator_node["ssh_username"],
        orchestrator_node["ssh_key_path"],
    )
    async with ssh:
        if await install_docker(ssh):
            if await install_bacalhau(ssh):
                if not await post_install_check(ssh):
                    logging.error("Post-installation validation failed.")
                    sys.exit(1)
                await setup_orchestrator_node(ssh)
            else:
                logging.error("Bacalhau installation failed.")
                sys.exit(1)
        else:
            logging.error("Docker installation failed.")
            sys.exit(1)

    logging.info("Starting parallel threads")
    semaphore = asyncio.Semaphore(5)
    await asyncio.gather(
        *[
            setup_compute_node_fn(
                semaphore, machine, orchestrator_node, orchestrator_node_public_ip, idx
            )
            for idx, machine in enumerate(machines)
        ]
    )


async def setup_compute_node_fn(
    semaphore, machine, orchestrator_node, orchestrator_node_public_ip, idx
):
    async with semaphore:
        if machine == orchestrator_node:
            return
        public_ip = next(
            (ip["public"] for ip in machine["ip_addresses"] if "public" in ip), None
        )
        if not public_ip:
            logging.error(
                f"No public IP found for compute node {machine['name']}. Skipping..."
            )
            return

        ssh = await ssh_connect(
            public_ip, machine["ssh_username"], machine["ssh_key_path"]
        )
        async with ssh:
            if await install_docker(ssh):
                logging.info(f"Installed Docker on {machine['name']}")
                if await install_bacalhau(ssh):
                    logging.info(f"Installed Bacalhau on {machine['name']}")
                    await configure_compute_node(ssh, orchestrator_node_public_ip, idx)
                else:
                    logging.error(
                        f"Bacalhau installation failed on compute node {machine['name']}. Skipping..."
                    )
            else:
                logging.error(
                    f"Docker installation failed on compute node {machine['name']}. Skipping..."
                )


async def configure_compute_node(ssh, orchestrator_node_public_ip, idx):
    logging.debug("Configuring compute node")

    compute_node_type_args = (
        f"--node-type=compute "
        f"--labels=count={idx} --orchestrators={orchestrator_node_public_ip}"
    )
    service_content = SYSTEMD_SERVICE.format(node_type_args=compute_node_type_args)

    # Write to a temporary file
    temp_path = "/tmp/bacalhau.service"

    try:
        sftp = await ssh.start_sftp_client()
        async with sftp.open(temp_path, "w") as service_file:
            await service_file.write(service_content)

        # Move the file to the correct location using sudo
        move_cmd = f"sudo mv {temp_path} /etc/systemd/system/bacalhau.service"
        await ssh_exec_command(ssh, move_cmd)

        # Create /data directory
        await ssh_exec_command(ssh, "sudo mkdir -p /data && sudo chmod 777 /data")

        fields_to_set = ["node.network.orchestrators", "node.clientapi.host"]

        set_commands = []
        for field in fields_to_set:
            set_commands.append(
                f"sudo bacalhau config set {field} {orchestrator_node_public_ip}"
            )
            set_commands.append(
                f"bacalhau config set {field} {orchestrator_node_public_ip}"
            )
        bulk_command = " && ".join(set_commands)
        await ssh_exec_command(ssh, bulk_command)

        print(bulk_command)
        await ssh_exec_command(ssh, bulk_command)

        await ssh_exec_command(ssh, "sudo systemctl enable bacalhau")
        await ssh_exec_command(ssh, "sudo systemctl daemon-reload")
        await ssh_exec_command(ssh, "sudo systemctl restart bacalhau")

        logging.info("Compute node configured successfully.")

    except Exception as e:
        logging.error(f"Failed to configure compute node: {e}")
        return None
    finally:
        if sftp:
            sftp.exit()


async def fetch_and_print_bacalhau_run_details(machine):
    logging.debug(f"Fetching bacalhau.run details for {machine['name']}")

    ssh = await ssh_connect(
        machine["ip_addresses"][1]["public"],
        machine["ssh_username"],
        machine["ssh_key_path"],
    )

    async with ssh:
        # Run the command to get the JSON output
        command = "sudo bacalhau config list --output json"
        output, error = await ssh_exec_command(ssh, command)

        if error:
            logging.error(f"Error running command: {error}")
        else:
            try:
                # Parse the JSON output
                data = json.loads(output)

                # Find the value of node.network.orchestrators
                node_network_orchestrators = None
                for item in data:
                    if item["Key"] == "node.network.orchestrators":
                        node_network_orchestrators = item["Value"]
                        break

                if node_network_orchestrators:
                    logging.info(
                        f"node.network.orchestrators: {node_network_orchestrators}"
                    )
                    print(
                        f"node.network.orchestrators for {machine['name']}: {node_network_orchestrators}"
                    )
                else:
                    logging.warning(
                        "node.network.orchestrators not found in the JSON output"
                    )

            except json.JSONDecodeError as e:
                logging.error(f"Error parsing JSON: {e}")

            return node_network_orchestrators


def get_ssh_connect_string(ssh):
    with open("MACHINES.json", "r") as f:
        machines = json.load(f)

    while True:
        machine = random.choice(machines)
        public_ip = next(
            (ip["public"] for ip in machine["ip_addresses"] if "public" in ip), None
        )
        if not public_ip:
            print(f"No public IP found for machine {machine['name']}. Skipping...")
            continue

        try:
            ssh.connect(
                public_ip,
                username=machine["ssh_username"],
                key_filename=machine["ssh_key_path"],
            )

            # Check if a different shell is already logged in
            stdin, stdout, stderr = ssh.exec_command("who")
            output = stdout.read().decode().strip()
            if output:
                print(
                    f"A different shell is already logged into {machine['name']}. Skipping..."
                )
                ssh.close()
                continue

            ssh_connect_string = f"ssh -i {machine['ssh_key_path']} {machine['ssh_username']}@{public_ip}"
            print(ssh_connect_string)
            ssh.close()
            break

        except Exception as e:
            print(f"Failed to connect to {machine['name']}: {str(e)}")
            ssh.close()
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Bacalhau on Azure VMs")
    parser.add_argument("--deploy", action="store_true", help="Deploy Bacalhau on VMs")
    parser.add_argument(
        "--fetch-run",
        action="store_true",
        help="Fetch and print the bacalhau.run file from the first node with a public IP",
    )
    parser.add_argument(
        "--get-ssh",
        action="store_true",
        help="Get a random SSH connect string for a node with a public IP",
    )
    args = parser.parse_args()

    if not args.deploy and not args.fetch_run and not args.get_ssh:
        parser.print_help()
        exit(1)

    if not os.path.exists("MACHINES.json"):
        logging.error("MACHINES.json file not found.")
        exit(1)

    with open("MACHINES.json", "r") as f:
        machines = json.load(f)

    if args.deploy:
        orchestrator_node, machines = identify_orchestrator_node(machines)
        asyncio.run(deploy_bacalhau(orchestrator_node, machines))

    if args.fetch_run:
        if not machines:
            logging.error("No machines configured.")
            exit(1)

        # Find the first node with a public IP
        first_compute_node = next(
            (machine for machine in machines if not machine["is_orchestrator_node"]),
            None,
        )

        if not first_compute_node:
            logging.error("No compute node found.")
            exit(1)

        try:
            node_network_orchestrators = asyncio.run(
                fetch_and_print_bacalhau_run_details(first_compute_node)
            )

            # Print out a formatted string with the node.network.orchestrators that can be used to export
            print(f"export BACALHAU_CLIENT_API_HOST={node_network_orchestrators[0]}")

        except Exception as e:
            logging.error(f"Failed to fetch bacalhau.run details: {str(e)}")

    if args.get_ssh:
        get_ssh_connect_string()
