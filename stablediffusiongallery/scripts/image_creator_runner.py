import os
import time
from pathlib import Path
from sys import argv

import downloader
from apscheduler.schedulers.background import BackgroundScheduler


def job(outputDir: str, numberToList: int) -> None:
    print(f"Executing creator - {outputDir} - # of images to create {numberToList}")
    command = "/gunicorn/add_many_images.sh %s %s" % ("pintura-test", 5)
    downloader.executeCommand(command)


if __name__ == "__main__":
    # if the first argument is set, use that as the seconds between each run
    secondsBetweenRun = int(argv[1]) if len(argv) > 1 else os.environ.get("SECONDS_BETWEEN_IMAGE_CREATES", 60)

    # If the second argument is set, use that as the label, otherwise use the env variable
    label = argv[2] if len(argv) > 2 else os.environ.get("LABEL", "pintura-image-creator-default")

    # If the third argument is set, use that as the number of images to create, otherwise use the env variable
    numberToCreate = argv[3] if len(argv) > 3 else os.environ.get("NUMBER_TO_CREATE", 5)

    # If the fourth argument is set, use that as the pid file, otherwise use the default
    pidFile = argv[4] if len(argv) > 4 else "/var/run/bacalhau-image-creator-runner.pid"

    # Exit if the pid file exists
    if Path(pidFile).exists():
        print("Pid file exists. Exiting.")
        exit(0)

    # Us os.getpid() to get the process id and write it to the pid file
    with open(pidFile, "w") as f:
        f.write(str(os.getpid()))

    # creating the BackgroundScheduler object
    scheduler = BackgroundScheduler()
    # setting the scheduled task
    scheduler.add_job(func=job, trigger="interval", args=[label, numberToCreate], seconds=secondsBetweenRun)
    # starting the scheduled task using the scheduler object
    scheduler.start()
    try:
        # To simulate application activity (which keeps the main thread alive).
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary but recommended
        scheduler.shutdown()
    finally:
        # Remove the pid file
        os.remove(pidFile)
