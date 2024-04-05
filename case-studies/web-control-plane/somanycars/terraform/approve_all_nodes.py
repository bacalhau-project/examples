import json
import subprocess
import os


def approve_all_nodes():
    # Print out the current BACALHAU_CLIENT_ID
    client_id = os.environ.get("BACALHAU_NODE_CLIENTAPI_HOST")
    print(f"Current BACALHAU_CLIENT_ID: {client_id}")
    
    # Get the bacalhau requester node IP
    nodes = subprocess.run(
        ["bacalhau", "node", "list", "--output", "json"], capture_output=True
    )
    nodes = json.loads(nodes.stdout)
    
    print("Total nodes: ", len(nodes))

    # Loop through all nodes and approve them
    for node in nodes:
        node_id = node["NodeID"]
        if node["Approval"] != "PENDING":
            print(f"NODE {node_id} not pending - already approved. 😀")
            continue
        else:
            # Run a subprocess to approve the node, but squelch the output
            subprocess.run(
                ["bacalhau", "node", "approve", node_id], capture_output=True
            )
            print(f"NODE {node_id} approved - ✅")

    print("All nodes approved.")


if __name__ == "__main__":
    approve_all_nodes()
