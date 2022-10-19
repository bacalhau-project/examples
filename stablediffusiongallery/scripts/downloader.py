import json
import os
import re
import shutil
import subprocess
import tempfile
from multiprocessing import Pool
from pathlib import Path
from sys import argv, stderr
from typing import Tuple

defaultOutputdir = "./outputs"
defaultCommand = "bacalhau list -n %s --output json"
defaultNumberToList = 100


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
            if len(files) > 0:
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
    tempOutputVolumePath = Path(tempOutputDir) / "volumes" / "outputs"

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

    jobs = json.loads(stdout)

    ids = []
    # For loop where we filter the jobs based on the status and the Annotation
    for job in jobs:
        nodes = job["JobState"]["Nodes"]
        for nodeId in nodes:
            shard = nodes[nodeId]["Shards"]
            for s in shard:
                state = shard[s]["State"]
                if (
                    state == "Completed"
                    and "Annotations" in job["Spec"]
                    and "pintura-test" in job["Spec"]["Annotations"]
                    and "RunOutput" in shard[s]
                ):
                    # Regex to see if the download got copied over properly
                    regex = re.compile(r"Copying \/inputs\/.*? to \/outputs")
                    if len(regex.findall(shard[s]["RunOutput"]["stdout"])) > 0:
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


# If main, execute with default settings
if __name__ == "__main__":
    # If first argument is set, use that as the output directory
    outputDir = argv[1] if len(argv) > 1 else defaultOutputdir

    # If second argument is set, use that as the number of jobs to list
    numberToList = argv[2] if len(argv) > 2 else defaultNumberToList

    # If third argument is set, use that as the pid file (mostly for debugging)
    pidFile = argv[3] if len(argv) > 3 else "/var/run/bacalhau-downloader.pid"

    # Exit if the pid file exists
    if Path(pidFile).exists():
        print("Pid file exists. Exiting.")
        exit(0)

    # Create the pid file
    Path(pidFile).touch()

    try:
        downloadImages(outputDir, numberToList)
    finally:
        # Remove the pid file
        Path(pidFile).unlink()
