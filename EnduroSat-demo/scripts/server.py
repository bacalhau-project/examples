#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastapi",
#     "uvicorn",
# ]
# ///

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONTAINER_PREFIX = "bacalhau_node"
AUTH_TOKEN = "abrakadabra1234!@#"
BANDWIDTH_FILE = "/mnt/local_files/config/bandwidth.txt"


def run_shell_script(script_path):
    try:
        result = subprocess.run([script_path], capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"Script executed successfully: {script_path}"
        else:
            return False, f"Error executing {script_path}: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Execution failed: {str(e)}"

def authenticate(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/close-network")
async def close_ports(request: Request):
    authenticate(request)
    success, message = run_shell_script("/scripts/disable-network.sh")
    return {"status": "success" if success else "error", "message": message}

@app.post("/open-network")
async def open_ports(request: Request):
    authenticate(request)
    success, message = run_shell_script("/scripts/enable-network.sh")
    return {"status": "success" if success else "error", "message": message}
class BandwidthRequest(BaseModel):
    value: str

@app.post("/set-bandwidth")
async def set_bandwidth(request: Request, body: BandwidthRequest):
    authenticate(request)
    bandwidth = body.value.upper()
    if bandwidth not in {"LOW", "HIGH"}:
        raise HTTPException(status_code=400, detail="Invalid value. Must be 'LOW' or 'HIGH'.")

    os.makedirs(os.path.dirname(BANDWIDTH_FILE), exist_ok=True)
    with open(BANDWIDTH_FILE, "w") as f:
        f.write(bandwidth)

    return {"status": "success", "new_value": bandwidth}

@app.get("/get-bandwidth")
async def get_bandwidth(request: Request):
    authenticate(request)
    try:
        with open(BANDWIDTH_FILE, "r") as f:
            value = f.read().strip().upper()
    except FileNotFoundError:
        value = "LOW"   # fallback default

    return {"status": "success", "current_value": value}
