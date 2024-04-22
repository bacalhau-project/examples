from glob import glob

workers = 1
timeout = 120
chdir = "/app"
access_logfile = "/var/log/uvicorn/access.log"
error_logfile = "/var/log/uvicorn/error.log"
bind = ["0.0.0.0:14041", "[::1]:16861"]
worker_class = "uvicorn.workers.UvicornWorker"
