#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "flask",
#     "gunicorn",
# ]
# ///

import logging
import subprocess

from flask import Flask, jsonify

# Disable Flask logging
log = logging.getLogger("werkzeug")
log.disabled = True
app = Flask(__name__)
app.logger.disabled = True

CONTAINER_PREFIX = "bacalhau_node"


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


@app.route("/healthz")
def healthz():
    is_healthy, message = check_docker_health()
    response = {"status": "healthy" if is_healthy else "unhealthy", "message": message}
    return jsonify(response), 200 if is_healthy else 503


@app.errorhandler(404)
def all_routes(e):
    return "", 404


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
        "bind": "0.0.0.0:80",
        "workers": 2,
        "accesslog": None,
        "errorlog": None,
        "worker_class": "sync",
        "timeout": 30,
        "logger_class": "gunicorn.glogging.Logger",
        "loglevel": "critical",
        "disable_redirect_access_to_syslog": True,
        "capture_output": False,
    }

    StandaloneApplication(app, options).run()
