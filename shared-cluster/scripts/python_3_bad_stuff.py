import os
import random
import subprocess
from pathlib import Path

import requests

debug = os.environ.get("DEBUG", "false").lower() == "true"


# Function to print results
def print_result(action, success, message):
    if success:
        print(f"❌ {action}: {message}")
    else:
        print(f"✅ {action}: {message}")


# 1. Read /etc/passwd
try:
    with open("/etc/passwd", "r") as f:
        content = f.read()

        # /etc/passwd comes from root node, not container
        if "azureuser" in content:
            print_result("Read /etc/passwd", True, "azureuser found in /etc/passwd")
        else:
            print_result(
                "Read /etc/passwd", False, "azureuser not found in /etc/passwd"
            )
except Exception:
    print_result("Read /etc/passwd", False, "Error reading /etc/passwd")

# 2. Send content to a website
try:
    response = requests.post("http://example.com", data={"key": "value"})
    print_result("Send content to a website", True, "Content sent to example.com")
except Exception:
    print_result(
        "Send content to a website", False, "Error sending content to example.com"
    )

# 3. Run a binary on Linux
try:
    # Try to run 'bacalhau' which is only on the root node
    subprocess.run(["/usr/local/bin/bacalhau"], check=True)
    print_result(
        "Run a binary on Linux",
        True,
        "bacalhau ran correctly (container had access to binaries on the root.)",
    )
except Exception:
    print_result(
        "Run a binary on Linux",
        False,
        "Error running bacalhau (container did not have access to binaries on the root node)",
    )

# 6. Open a network socket
try:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", 80))
    print_result(
        "Open a network socket", True, "Opened a network socket to localhost:80"
    )
except Exception:
    print_result(
        "Open a network socket", False, "Error opening a network socket to localhost:80"
    )


# 9. Delete a file in the network share
try:
    share_path = Path("/azureshare")
    files = [f for f in share_path.iterdir() if f.is_file()]
    path_to_file = Path(share_path, random.choice(files))
    path_to_file.unlink()
    print_result(
        "Delete a file in the network share",
        True,
        f"Deleted file: {path_to_file.name}",
    )
except Exception as e:
    print_result(
        "Delete a file in the network share",
        False,
        f"Error deleting file: {e}",
    )
