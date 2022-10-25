#!python3
import os
import string
import subprocess
from pathlib import Path
from random import randint, shuffle
from turtle import dot
from typing import List, Tuple

import dotenv
import paramiko
import regex as re
import semver
from paramiko import AutoAddPolicy, SSHClient

# Clear all environment variables
path = os.environ["PATH"]
for i in os.environ:
    os.environ.pop(i)
dotenv.load_dotenv()

# Make a copy to make it easier to read in Python
envDict = os.environ.copy() | dict(PATH=path)

# Shell out to CLI to export poetry requirements to scripts/requirements.txt
def executeCommand(cmdAndArgs: List, cwd: str = ".") -> Tuple[str, int]:
    p = subprocess.Popen(
        cmdAndArgs,
        cwd=cwd,
        stdout=subprocess.PIPE,
        shell=False,
        env=envDict,
    )
    stdout = p.communicate()[0]
    exitCode = p.returncode
    return stdout.decode("utf-8"), exitCode


def injectEnvVars(envVars: dict) -> str:
    envVarList = []
    for key, value in envVars.items():
        envVarList.append(f"{key}={value}")

    return " ".join(envVarList)


print("Checking version of rsync...")
stdout, exitCode = executeCommand(["rsync", "--version"])
r = re.compile(r"rsync\s+version\s+(\d+\.\d+\.\d+)")
stdoutRegex = r.search(stdout)

if not stdoutRegex:
    raise Exception("Could not find rsync version")

stdoutSemver = semver.parse(stdoutRegex.group(1))
if stdoutSemver["major"] < 3:
    raise Exception(
        "rsync version must be at least 3.0.0. Update rsync and try again (on a mac, use `brew install rsync`)."
    )


print("Starting exporting requirements.txt ... ", end="")
exportRequirementsCmd = [
    "poetry",
    "export",
    "-f",
    "requirements.txt",
    "-o",
    "scripts/requirements.txt",
    "--without-hashes",
]
stdout, exitCode = executeCommand(exportRequirementsCmd)

if exitCode != 0:
    print("Failed to export poetry requirements to scripts/requirements.txt")
    exit(exitCode)
print("done")


# Run terraform init in shell
print("Starting init-ing the terraform directory ... ", end="")
stdout, exitCode = executeCommand(["terraform", "init"], cwd="tf")
if exitCode != 0:
    print("Failed to run terraform init.")
    exit(exitCode)
print("done")

# Run terraform plan in shell
print("Starting terraform plan ... ", end="")
stdout, exitCode = executeCommand(["terraform", "plan", "-out", "tf.plan"], cwd="tf")
if exitCode != 0:
    print("Failed to run terraform plan.")
    exit(exitCode)
print("done")

# Run terraform apply in shell
print("Starting terraform apply ... ", end="")
stdout, exitCode = executeCommand(["terraform", "apply", "tf.plan"], cwd="tf")
if exitCode != 0:
    print("Failed to run terraform apply.")
    exit(exitCode)
print("done")

# Get IP address of instance
print("Getting IP address of instance ... ", end="")
getIPCmd = ["terraform", "output", "-raw", "ip_address"]
stdout, exitCode = executeCommand(getIPCmd, cwd="tf")

if exitCode != 0:
    print("Failed to get IP address of instance:.")
    exit(exitCode)
print("done")

ipAddress = stdout.strip()
print("IP Address: %s" % ipAddress)

allChars = string.ascii_lowercase + string.ascii_uppercase + string.digits
sqlLiteKey = "".join([allChars[randint(0, len(allChars) - 1)] for _ in range(30)])

dotenv.set_key(".env", "SQLITE_KEY", sqlLiteKey)
dotenv.set_key(".env", "IP", ipAddress)

# Setup SSH connection
ssh = SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(
    ipAddress,
    username="ubuntu",
    key_filename=os.environ.get("SSH_KEY_PATH"),
)

# Copy scripts/ directory to instance using scp
sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
print("rsync-ing scripts directory to instance ... ", end="")
temp_remote_path = "/tmp/gunicorn_scripts"
rsyncCommand = [
    "rsync",
    "-a",
    "-e",
    "ssh",
    "--chmod=D0700,F0700",
    "--exclude",
    '"scripts/__pycache__"',
    "scripts/",
    "ubuntu@%s:%s" % (ipAddress, temp_remote_path),
]
print(" ".join(rsyncCommand))
stdout, exitCode = executeCommand(rsyncCommand)
if exitCode != 0:
    print("Failed to rsync contents to temp dir of instance:.")
    exit(exitCode)
print("done")

# Moving gunicorn finals to final location
print("Moving gunicorn files to final location ... ", end="")
remoteRsyncCommand = [
    "sudo",
    "rsync",
    "-Ia",
    "--remove-source-files",
    "--chmod=D0770,F0770",
    "--chown=www-data:www-data",
    f"{temp_remote_path}/",
    "/gunicorn",
]
print(" ".join(remoteRsyncCommand))
stdin, stdout, stderr = ssh.exec_command(" ".join(remoteRsyncCommand))
if exitCode != 0:
    print("Failed to move gunicorn files to final location:.")
    exit(exitCode)

print("done")

e = injectEnvVars(envDict)

# Run the install script on the remote machine
print("Running install nginx script on remote machine ... ", end="")
stdin, stdout, stderr = ssh.exec_command(f"{e} sudo -E /gunicorn/install_nginx.sh")
if exitCode != 0:
    print("Failed to run install nginx script on remote machine:.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")

# Run install bacalhau script on the remote machine
print("Running install bacalhau script on remote machine ... ", end="")
stdin, stdout, stderr = ssh.exec_command(
    "sudo -E bash /gunicorn/install_bacalhau.sh 2&1> /dev/null", environment=envDict
)
if exitCode != 0:
    print("Failed to run install bacalhau script on remote machine:.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")

# Run install bacalhau downloader script on the remote machine
print("Running install bacalhau downloader script on remote machine ... ", end="")
stdin, stdout, stderr = ssh.exec_command(f"{e} sudo -E /gunicorn/install_bacalhau_downloader.sh")
if exitCode != 0:
    print("Failed to run install bacalhau downloader script on remote machine:.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")

# Run install bacalhau image creator script on the remote machine
print("Running install bacalhau image creator script on remote machine ... ", end="")
stdin, stdout, stderr = ssh.exec_command(f"{e} sudo -E /gunicorn/install_bacalhau_image_creator.sh")
if exitCode != 0:
    print("Failed to run install bacalhau image creator script on remote machine:.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")

# Split out into its own file so we can update independantly
executeCommand(["./update_website.sh"])

# Run restart all services script on the remote machine
print("Running restart all services script on remote machine ... ", end="")
stdin, stdout, stderr = ssh.exec_command(f"{e} sudo -E /gunicorn/restart_all_services.sh")
if exitCode != 0:
    print("Failed to run restart all services script on remote machine:.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")

# Make all .sh files in the /gunicorn readable only by root
print("Making all .sh files in /gunicorn readable only by root:group... ", end="")
stdin, stdout, stderr = ssh.exec_command(
    f"{e} sudo -E chmod 770 /gunicorn/*.sh && {e} sudo -E chown -R www-user:user-data /gunicorn"
)
if exitCode != 0:
    print("Failed to make all .sh files in /gunicorn readable only by root:group.")
    print(f"Stdout: {stdout.read()}")
    print(f"Stderr: {stderr.read()}")
    exit(exitCode)
print("done")
