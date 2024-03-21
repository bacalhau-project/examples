from glob import glob

workers=1
log_level="debug"
reload=True
timeout=120
chdir="/Users/daaronch/code/bacalhau-examples/case-studies/web-control-plane/lb/server-files/home/itsadashuser/itsadashapp"
reload_extra_file="templates/justicons_dashboard.html"
bind="127.0.0.1:5002"
log_file="-"