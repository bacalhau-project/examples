import os
import sys
import json
import paramiko
import time
import argparse
import logging

# Setup basic configuration for logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_ed25519')
BACALHAU_INSTALL_CMD = """
curl -sL 'https://get.bacalhau.org/install.sh?dl=BACA41A0-a5e9-40db-801c-dfaf9af6e05f' | sudo bash
"""
BACALHAU_START_CMD = "bacalhau serve"
SYSTEMD_SERVICE = """
[Unit]
Description=Bacalhau Service
After=network.target

[Service]
ExecStart=/usr/local/bin/bacalhau {node_type_args}
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""

def ssh_connect(hostname, username, key_filename):
    logging.debug(f"Connecting to {hostname} as {username}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, key_filename=key_filename)
    return ssh

def install_bacalhau(ssh):
    logging.debug("Starting Bacalhau installation")
    try:
        stdin, stdout, stderr = ssh.exec_command('curl -sSL https://get.bacalhau.org/install.sh?dl=BACA41A0-a5e9-40db-801c-dfaf9af6e05f | sudo bash')
        output = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            logging.error(f"Installation errors: {error}")
            return False
        logging.info("Installation output:")
        logging.info(output)
        return True
    except Exception as e:
        logging.error(f"Exception during installation: {str(e)}")
        return False

def install_bacalhau(ssh):
    logging.debug("Downloading Bacalhau installation script")
    # Download the installation script to /tmp
    stdin, stdout, stderr = ssh.exec_command("curl -sSL 'https://get.bacalhau.org/install.sh?dl=BACA41A0-a5e9-40db-801c-dfaf9af6e05f' -o /tmp/install_bacalhau.sh")
    
    logging.debug("Running Bacalhau installation script")
    # Execute the script from /tmp
    stdin, stdout, stderr = ssh.exec_command('bash /tmp/install_bacalhau.sh')
    output = stdout.read().decode()
    error = stderr.read().decode()
    
    if error:
        logging.error(f"Installation errors: {error}")
        return False
    logging.info("Installation output:")
    logging.info(output)
    return True

def post_install_check(ssh):
    logging.debug("Checking Bacalhau installation")
    try:
        stdin, stdout, stderr = ssh.exec_command('bacalhau version')
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        logging.debug(f"Command output: {output}")
        logging.debug(f"Command error: {error}")
        if 'bacalhau version' in output:
            logging.info("Bacalhau installed successfully.")
            return True
        else:
            logging.error("Bacalhau installation check failed.")
            return False
    except Exception as e:
        logging.error(f"Exception during post-install check: {str(e)}")
        return False
    
def setup_first_node(ssh):
    logging.debug("Setting up the first node")
    stdin, stdout, stderr = ssh.exec_command(f'sudo nohup {BACALHAU_START_CMD} &')
    time.sleep(10)
    logging.debug("Copying bacalhau.run to /tmp")
    ssh.exec_command('sudo cp /root/.bacalhau/bacalhau.run /tmp/bacalhau.run && sudo chmod 644 /tmp/bacalhau.run')

    sftp = ssh.open_sftp()
    with sftp.file('/tmp/bacalhau.run', 'r') as f:
        details = f.read().decode()
    sftp.close()

    ssh.exec_command('sudo rm /tmp/bacalhau.run')
    ssh.exec_command('sudo pkill -f "bacalhau serve"')
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

def setup_compute_node(ssh, orchestrator_info):
    logging.debug("Setting up compute node")
    node_type_args = f"--node-type=compute --network=nats --orchestrators={orchestrator_info['BACALHAU_NODE_NETWORK_ORCHESTRATORS']} --private-internal-ipfs --ipfs-swarm-addrs={orchestrator_info['BACALHAU_NODE_IPFS_SWARMADDRESSES']}"
    service_content = SYSTEMD_SERVICE.format(node_type_args=node_type_args)

    # Write to a temporary file
    temp_path = '/tmp/bacalhau.service'
    sftp = ssh.open_sftp()
    with sftp.file(temp_path, 'w') as service_file:
        service_file.write(service_content)
    sftp.close()

    # Move the file to the correct location using sudo
    move_cmd = f'sudo mv {temp_path} /etc/systemd/system/bacalhau.service'
    ssh.exec_command(move_cmd)

    ssh.exec_command('sudo systemctl enable bacalhau')
    ssh.exec_command('sudo systemctl start bacalhau')

def deploy_bacalhau(machines):
    logging.debug("Starting deployment of Bacalhau")
    orchestrator_node = None

    # Check if the orchestrator node is already set
    for machine in machines:
        if machine.get('is_orchestrator_node', False):
            orchestrator_node = machine
            break

    if not orchestrator_node:
        # Designate the orchestrator node
        for machine in machines:
            if machine['ip_addresses']:
                for ip_address in machine['ip_addresses']:
                    if 'public' in ip_address:
                        orchestrator_node = machine
                        machine['is_orchestrator_node'] = True  # Mark this machine as the orchestrator node
                        break
            if orchestrator_node:
                break

        # Update the MACHINES.json file
        with open("MACHINES.json", "w") as f:
            json.dump(machines, f, indent=4)

    if not orchestrator_node:
        logging.error("No suitable orchestrator node found.")
        return

    # Proceed with deployment using the orchestrator node
    public_ip = next((ip['public'] for ip in orchestrator_node['ip_addresses'] if 'public' in ip), None)
    if not public_ip:
        logging.error("No public IP found for the orchestrator node.")
        return

    ssh = ssh_connect(public_ip, orchestrator_node['ssh_username'], orchestrator_node['ssh_key_path'])
    try:
        if install_bacalhau(ssh):
            if not post_install_check(ssh):
                logging.error("Post-installation validation failed.")
                sys.exit(1)
        else:
            logging.error("Bacalhau installation failed.")
            sys.exit(1)    
    finally:
        ssh.close()
            
def fetch_and_print_bacalhau_run_details(ssh):
    logging.debug("Fetching bacalhau.run details")
    try:
        # Using sudo to cat the file content
        stdin, stdout, stderr = ssh.exec_command('sudo cat /root/.bacalhau/bacalhau.run')
        details = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            logging.error(f"Error reading bacalhau.run: {error}")
            return
        print("Contents of bacalhau.run:")
        print(details)
    except Exception as e:
        logging.error(f"Failed to fetch bacalhau.run details: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Bacalhau on Azure VMs")
    parser.add_argument('--deploy', action='store_true', help="Deploy Bacalhau on VMs")
    parser.add_argument('--fetch-run', action='store_true', help="Fetch and print the bacalhau.run file from the first node with a public IP")
    args = parser.parse_args()

    if not args.deploy and not args.fetch_run:
        parser.print_help()
        exit(1)

    if not os.path.exists("MACHINES.json"):
        logging.error("MACHINES.json file not found.")
        exit(1)

    with open("MACHINES.json", "r") as f:
        machines = json.load(f)

    if args.deploy:
        deploy_bacalhau(machines)
    
    if args.fetch_run:
        if not machines:
            logging.error("No machines configured.")
            exit(1)
        
        # Find the first node with a public IP
        first_node_with_public_ip = None
        for machine in machines:
            for ip_address in machine['ip_addresses']:
                if 'public' in ip_address:
                    first_node_with_public_ip = machine
                    break
            if first_node_with_public_ip:
                break

        if not first_node_with_public_ip:
            logging.error("No machine with a public IP found.")
            exit(1)

        public_ip = next((ip['public'] for ip in first_node_with_public_ip['ip_addresses'] if 'public' in ip), None)
        if not public_ip:
            logging.error("No public IP found for the first node with a public IP.")
            exit(1)

        ssh = ssh_connect(public_ip, first_node_with_public_ip['ssh_username'], first_node_with_public_ip['ssh_key_path'])
        try:
            fetch_and_print_bacalhau_run_details(ssh)
        finally:
            ssh.close()