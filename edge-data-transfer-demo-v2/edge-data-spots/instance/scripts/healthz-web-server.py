#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "flask",
#     "gunicorn",
#     "flask_cors",
# ]
# ///

import logging
import subprocess
import shutil
import os
import re
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

# Disable Flask logging
log = logging.getLogger("werkzeug")
log.disabled = True
app = Flask(__name__)
app.logger.disabled = True

CORS(app, resources={r"/*": {"origins": "*"}})

CONTAINER_PREFIX = "bacalhau_node"
AUTH_TOKEN = "abrakadabra1234!@#"


def check_docker_health():
    try:
        cmd = f"docker ps --filter name=^/{CONTAINER_PREFIX} --format '{{{{.Status}}}}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if "(healthy)" in result.stdout:
            return True, "Container is healthy"
        elif result.stdout.strip():
            return False, "Container is running but not healthy"
        else:
            return False, f"No containers found matching prefix '{CONTAINER_PREFIX}'"
    except Exception as e:
        return False, f"Error checking health: {str(e)}"


def run_shell_script(script_path):
    try:
        result = subprocess.run(["sudo", script_path], capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"Script executed successfully: {script_path}"
        else:
            return False, f"Error executing {script_path}: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Execution failed: {str(e)}"


def authenticate():
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {AUTH_TOKEN}":
        abort(401, description="Unauthorized")


@app.route("/nfs-healthz")
def nfs_healthz():
    authenticate()
    mount_point = "/mnt/data"
    if not os.path.ismount(mount_point):
        return jsonify({"status": "unhealthy", "message": f"{mount_point} is not mounted"}), 503

    try:
        # użycie `timeout` + `ls` na /mnt/data
        result = subprocess.run(
            ["timeout", "1", "ls", "-1", mount_point],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return jsonify({"status": "healthy", "message": f"NFS mount {mount_point} is healthy"}), 200
        else:
            return jsonify({
                "status": "unhealthy",
                "message": f"NFS I/O failed or timeout. Exit code: {result.returncode}, stderr: {result.stderr.strip()}"
            }), 503
    except Exception as e:
        return jsonify({"status": "unhealthy", "message": f"Exception: {str(e)}"}), 503

@app.route("/healthz")
def healthz():
    is_healthy, message = check_docker_health()
    response = {"status": "healthy" if is_healthy else "unhealthy", "message": message}
    return jsonify(response), 200 if is_healthy else 503


@app.route("/close-network", methods=["POST"])
def close_ports():
    authenticate()
    success, message = run_shell_script("/opt/disable-network.sh")
    return jsonify({"status": "success" if success else "error", "message": message})


@app.route("/open-network", methods=["POST"])
def open_ports():
    authenticate()
    success, message = run_shell_script("/opt/enable-network.sh")
    return jsonify({"status": "success" if success else "error", "message": message})

@app.route("/close-nfs", methods=["POST"])
def close_nfs():
    authenticate()
    success, message = run_shell_script("/opt/disable-nfs.sh")
    return jsonify({"status": "success" if success else "error", "message": message})


@app.route("/open-nfs", methods=["POST"])
def open_nfs():
    authenticate()
    success, message = run_shell_script("/opt/enable-nfs.sh")
    return jsonify({"status": "success" if success else "error", "message": message})

@app.errorhandler(404)
def all_routes(e):
    return "", 404

def natural_sort_key(filename):
    match = re.search(r'(\d+)', filename)
    return int(match.group(1)) if match else float('inf')

@app.route("/file", methods=["GET"])
def list_files():
    authenticate()
    directory = "/mnt/data"
    try:
        files = [
            f for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        ]
        files_sorted = sorted(files, key=natural_sort_key)
        return jsonify({"files": files_sorted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/process_file", methods=["GET"])
def list_processed_files():
    authenticate()
    directory = "/bacalhau_data/metadata"
    try:
        files = [
            f for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        ]
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/clear-metadata", methods=["POST"])
def clear_metadata():
    authenticate()
    target_dir = "/bacalhau_data/metadata"
    try:
        if os.path.exists(target_dir):
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            return jsonify({"status": "success", "message": "Metadata directory cleared."})
        else:
            return jsonify({"status": "error", "message": f"Directory {target_dir} does not exist."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to clear directory: {str(e)}"}), 500



if __name__ == "__main__":
    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    options = {
        "bind": "0.0.0.0:9123",
        "workers": 16,
        "accesslog": None,
        "errorlog": None,
        "worker_class": "sync",
        "timeout": 15,
        "logger_class": "gunicorn.glogging.Logger",
        "loglevel": "critical",
        "disable_redirect_access_to_syslog": True,
        "capture_output": False,
    }

    StandaloneApplication(app, options).run()
