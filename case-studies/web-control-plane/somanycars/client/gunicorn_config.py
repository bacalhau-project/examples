from glob import glob

workers = 1
timeout = 120
chdir = "/app"
reload_extra_file = "templates/justicons_dashboard.html"
access_logfile = "/var/log/gunicorn/access.log"
error_logfile = "/var/log/gunicorn/error.log"
bind = ["0.0.0.0:14041", "[::1]:16861"]
worker_class = "uvicorn.workers.UvicornWorker"
