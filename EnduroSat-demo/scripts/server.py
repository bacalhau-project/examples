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
import subprocess

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
