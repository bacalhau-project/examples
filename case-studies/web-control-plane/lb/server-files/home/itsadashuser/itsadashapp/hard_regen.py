# Grab the output of gcloud compute instances list with all the internal IPs for
# a given site, named by the first argument. Then, post the IPs to the
# /home/itsadashuser/itsadashapp/sites/<site>.conf file as:
# 'server <internal_ip>:14041;'
# and restart the nginx service and gunicorn service.


def hard_regen():
    import os
    import re
    import subprocess
    import sys

    if len(sys.argv) != 2:
        print("Usage: hard_regen.py <site>")
        sys.exit(1)

    site = sys.argv[1]

    # Test to make sure it's the right form of "site" (e.g. "site.com")
    regex = re.compile(r"^([a-zA-Z0-9]+)\.\w+$")
    if not regex.match(site):
        print("Invalid site - should be of the form 'site.com'")
        sys.exit(1)

    domain_name = site.split(".")[0]
    execute_command = f"gcloud compute instances list --filter='name:{domain_name}' --format='value(networkInterfaces[0].networkIP)'"
    output = (
        subprocess.check_output(execute_command, shell=True).decode("utf-8").strip()
    )

    # Print the output for debugging
    print(output)

    blob_for_writing = ""
    for ip in output.split("\n"):
        blob_for_writing += f"server {ip}:14041;\n"

    # SSH into itsadash.work and write the output to the file
    ssh_command = f"ssh itsadashuser@itsadash.work 'echo {output} > /home/itsadashuser/itsadashapp/sites/{site}.conf'"
    os.system(ssh_command)

    # Restart the nginx service
    ssh_command = "ssh itsadashuser@itsadash.work 'sudo systemctl restart nginx'"
    os.system(ssh_command)

    # Restart the gunicorn service
    ssh_command = "ssh itsadashuser@itsadash.work 'sudo systemctl restart gunicorn'"
    os.system(ssh_command)


if __name__ == "__main__":
    hard_regen()
