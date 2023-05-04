import json
import os
import re
import shutil
import subprocess
import tempfile
from ast import arg
from multiprocessing import Pool
from pathlib import Path
from sys import argv, stderr
from typing import Tuple

defaultOutputdir = "./outputs"
defaultCommand = "bacalhau list -n %s --output json --all"
defaultNumberToList = 10


def executeCommand(cmd) -> Tuple[str, str, int]:
    p = subprocess.Popen([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    stdout, stderr = p.communicate()
    return (stdout, stderr, p.returncode)


def downloadFile(downloadParameters: Tuple) -> None:
    tempdir, outputDir, id = downloadParameters
    finalOutputDir = Path(outputDir) / id

    # If the finalOutputDir already exists, we can continue
    if finalOutputDir.exists():
        for root, dirs, files in os.walk(finalOutputDir):
            if len(files) > 1:
                # Don't care what's in it, just that it's not empty
                return
        # Since we're here, we know that the directory is empty
        print("Directory %s is empty but exists. Going forward with download." % finalOutputDir)
    else:
        # If it doesn't exist, we create it
        Path.mkdir(finalOutputDir, 0o755)

    tempOutputDir = Path(tempdir) / id

    # If the tempOutputDir doesn't exist, we create it
    if not tempOutputDir.exists():
        Path.mkdir(tempOutputDir, 0o755)

    # Get the id using bacalhau
    command = "bacalhau get " + id + " --output-dir " + str(tempOutputDir)
    print(f"Outputdir: {tempOutputDir}")

    # Execute the command
    executeCommand(command)

    # Move the image to the finalOutputDir
    tempOutputVolumePath = Path(tempOutputDir) / "outputs"

    tempOutputVolumePathString = str(tempOutputVolumePath)
    finalOutputDirString = str(finalOutputDir)

    if not tempOutputVolumePath.exists():
        print("Output path doesn't exist. Skipping.")
        return

    for f in os.listdir(str(tempOutputVolumePath)):
        print(f"Moving {f} to {finalOutputDir}")
        os.rename(tempOutputVolumePathString + "/" + f, finalOutputDirString + "/" + f)

    # Download bacalhau description to metadata file
    command = "bacalhau describe " + id
    stdout, stderr, exitCode = executeCommand(command)

    with open(os.path.join(finalOutputDirString, "metadata"), "wb") as m:
        m.write(stdout)


def downloadImages(outputDir: str, numberToList: int) -> None:
    commandWithNumber = defaultCommand % numberToList
    stdout, stderr, exitCode = executeCommand(commandWithNumber)

    try:
        jobs = json.loads(stdout)
    except:
        print("Error loading json from stdout. Exiting: %s" % stdout)
        exit(1)

    ids = []
    # For loop where we filter the jobs based on the status and the Annotation
    for job in jobs:
        if "Nodes" in job["JobState"]:
            nodes = job["JobState"]["Nodes"]
            for nodeId in nodes:
                shard = nodes[nodeId]["Shards"]
                for s in shard:
                    state = shard[s]["State"]
                    # Print annotations if there are any
                    if "Annotations" in shard[s]:
                        annotations = shard[s]["Annotations"]
                        for annotation in annotations:
                            print(annotation)
                    if (
                        state == "Completed"
                        and "Annotations" in job["Spec"]
                        and "pintura-sd" in job["Spec"]["Annotations"]
                        and "PublishedResults" in shard[s]
                    ):
                        ids.append(job["ID"])
    try:
        # Create temporary directory using system temp directory
        tempdir = Path(tempfile.mkdtemp())

        downloadParameters = []
        for id in ids:
            downloadParameters.append((tempdir, outputDir, id))

        # Execute downloadFile in a threadPool of 10
        Pool(10).map(downloadFile, downloadParameters)
    finally:
        # Remove the temporary directory
        shutil.rmtree(tempdir)

    # Request to local server to update the database
    executeCommand("curl -X POST http://localhost/updateDB")


# If main, execute with default settings
if __name__ == "__main__":
    if len(argv) < 3:
        print("Usage: python3 downloader.py <outputdir> <numberToList> <pidfile>", file=stderr)
        # stop run
        exit(1)

    # If first argument is set, use that as the output directory
    outputDir = argv[1] if len(argv) > 1 else defaultOutputdir

    # If second argument is set, use that as the number of jobs to list
    numberToList = argv[2] if len(argv) > 2 else defaultNumberToList

    # If third argument is set, use that as the pid file (mostly for debugging)
    pidFile = argv[3] if len(argv) > 3 else "/var/run/bacalhau-downloader.pid"

    # Exit if the pid file exists
    if argv[3] == "" and Path(pidFile).exists():
        print("Pid file exists. Exiting.")
        exit(0)

    # Create the pid file
    Path(pidFile).touch()

    try:
        downloadImages(outputDir, numberToList)
    finally:
        # Remove the pid file
        Path(pidFile).unlink()
