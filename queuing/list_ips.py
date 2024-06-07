import os
import json
import sys
import socket
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ServiceRequestError

def check_connectivity():
    try:
        response = requests.get('https://management.azure.com', timeout=5)
        print("Internet and Azure Management Endpoint reachable")
    except requests.ConnectionError:
        print("Failed to reach Azure Management Endpoint")
        sys.exit(1)

def check_dns_resolution():
    try:
        socket.gethostbyname('management.azure.com')
        print("DNS resolution for Azure Management Endpoint successful")
    except socket.error as e:
        print(f"DNS resolution failed: {e}")
        sys.exit(1)

def authenticate(subscription_id):
    try:
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        return client
    except Exception as e:
        print(f"Error during authentication: {e}")
        sys.exit(1)

def list_resources_with_tag(client, unique_id):
    print(f"Listing resources with tag 'uniqueId={unique_id}'")
    try:
        resources = client.resources.list(filter=f"tagName eq 'uniqueId' and tagValue eq '{unique_id}'")
    except ServiceRequestError as e:
        print(f"Failed to list resources: {e}")
        sys.exit(1)

    resources_dict = []
    machines_dict = []
    
    for resource in resources:
        resource_type = resource.type
        resource_name = resource.name
        resource_location = resource.location

        resource_info = {
            'name': resource_name,
            'location': resource_location,
            'ssh_username': "azureuser",
            'ssh_key_path': os.path.expanduser('~/.ssh/id_ed25519'),
            'ip_addresses': []
        }

        if resource_type == 'Microsoft.Compute/virtualMachines':
            try:
                detailed_resource = client.resources.get_by_id(resource.id, '2021-04-01')
            except ServiceRequestError as e:
                print(f"Failed to get details for resource {resource_name}: {e}")
                continue

            if detailed_resource.properties:
                network_profile = detailed_resource.properties.get('networkProfile')
                if network_profile:
                    for nic in network_profile.get('networkInterfaces', []):
                        nic_id = nic['id']
                        if nic_id:
                            try:
                                nic_details = client.resources.get_by_id(nic_id, '2021-04-01')
                            except ServiceRequestError as e:
                                print(f"Failed to get details for NIC {nic_id}: {e}")
                                continue
                            ip_configurations = nic_details.properties.get('ipConfigurations', [])
                            for ip_configuration in ip_configurations:
                                private_ip = ip_configuration['properties'].get('privateIPAddress', None)
                                public_ip_id = ip_configuration['properties'].get('publicIPAddress', {}).get('id')
                                if private_ip:
                                    resource_info['ip_addresses'].append({'private': private_ip})
                                if public_ip_id:
                                    try:
                                        public_ip_details = client.resources.get_by_id(public_ip_id, '2021-04-01')
                                    except ServiceRequestError as e:
                                        print(f"Failed to get details for public IP {public_ip_id}: {e}")
                                        continue
                                    public_ip = public_ip_details.properties.get('ipAddress', None)
                                    if public_ip:
                                        resource_info['ip_addresses'].append({'public': public_ip})
            machines_dict.append(resource_info)        

    with open("MACHINES.json", "w") as outfile:
        json.dump(machines_dict, outfile, indent=4)

    return machines_dict

def print_machine_details(machines):
    print(f"{'Name':<60} {'Private IP':<20} {'Public IP':<20} {'Location':<15} {'Orchestrator':<15}")
    print("-" * 135)
    for machine in machines:
        name = machine['name']
        location = machine['location']
        private_ip = next((ip['private'] for ip in machine['ip_addresses'] if 'private' in ip), 'N/A')
        public_ip = next((ip['public'] for ip in machine['ip_addresses'] if 'public' in ip), 'N/A')
        orchestrator_status = "Yes" if machine.get('is_orchestrator_node', False) else "No"
        print(f"{name:<60} {private_ip:<20} {public_ip:<20} {location:<15} {orchestrator_status:<15}")

def designate_orchestrator(machines):
    # Ensure at least one machine is available
    if not machines:
        print("No machines available.")
        return

    # Set the first machine as the orchestrator and the rest as not
    for index, machine in enumerate(machines):
        if index == 0:
            machine['is_orchestrator_node'] = True
        else:
            machine['is_orchestrator_node'] = False

    # Optionally, save the updated list back to the JSON file or handle it as needed
    with open("MACHINES.json", "w") as file:
        json.dump(machines, file, indent=4)

    return machines

if __name__ == "__main__":
    check_connectivity()
    check_dns_resolution()

    load_dotenv()
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

    if not subscription_id:
        print("Error: AZURE_SUBSCRIPTION_ID not found in .env file.")
        exit(1)

    unique_id = None
    if os.path.exists("UNIQUEID"):
        with open("UNIQUEID", "r") as f:
            unique_id = f.read().strip()
    
    if not unique_id:
        print("Error: UNIQUEID file not found.")
        exit(1)
    
    client = authenticate(subscription_id)
    machines = list_resources_with_tag(client, unique_id)
    
    designate_orchestrator(machines)
    print_machine_details(machines)

