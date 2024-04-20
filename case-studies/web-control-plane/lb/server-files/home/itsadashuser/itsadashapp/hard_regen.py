# Grab the output of gcloud compute instances list with all the internal IPs for
# a given site, named by the first argument. Then, post the IPs to the
# /home/itsadashuser/itsadashapp/sites/<site>.conf file as:
# 'server <internal_ip>:14041;'
# and restart the nginx service and gunicorn service.
import re
import subprocess
import sys


def execute_command(command: str):
    print(f"Executing: {command}")
    return subprocess.check_output(command, shell=True).decode("utf-8").strip()


def hard_regen():
    for site in ["justicons.org", "somanycars.org"]:
        hard_regen_site(site)

    # Restart the nginx service
    ssh_command = "ssh itsadashuser@itsadash.work 'sudo systemctl restart nginx'"
    execute_command(ssh_command)

    # Restart the gunicorn service
    ssh_command = "ssh itsadashuser@itsadash.work 'sudo systemctl restart gunicorn'"
    execute_command(ssh_command)


def hard_regen_site(site: str):
    if site is None:
        print("Need <site>")
        sys.exit(1)

    # Test to make sure it's the right form of "site" (e.g. "site.com")
    regex = re.compile(r"^([a-zA-Z0-9]+)\.\w+$")
    if not regex.match(site):
        print("Invalid site - should be of the form 'site.com'")
        sys.exit(1)

    domain_name = site.split(".")[0]
    ssh_command = f"gcloud compute instances list --filter='name:{domain_name}' --format='value(networkInterfaces[0].networkIP)'"
    output = execute_command(ssh_command)

    blob_for_writing = ""
    for ip in output.split("\n"):
        blob_for_writing += f"server {ip}:14041;\n"

    if not blob_for_writing:
        blob_for_writing = "server 127.0.0.1:14041;\n"

    # SSH into itsadash.work and write the output to the file
    ssh_command = f"ssh itsadashuser@itsadash.work 'echo \"{blob_for_writing}\" > /home/itsadashuser/itsadashapp/sites/{site}.conf'"
    execute_command(ssh_command)


if __name__ == "__main__":
    hard_regen()
