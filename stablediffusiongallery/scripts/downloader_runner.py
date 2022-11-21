import os
import time
from pathlib import Path
from sys import argv

import downloader
from apscheduler.schedulers.background import BackgroundScheduler


def job(outputDir: str, numberToList: int) -> None:
    print(f"Executing download - {outputDir} - # of jobs to list {numberToList}")
    downloader.downloadImages(outputDir, numberToList)


if __name__ == "__main__":
    # if the first argument is set, use that as the seconds between each run
    secondsBetweenRun = int(argv[1]) if len(argv) > 1 else 60

    # If the second argument is set, use that as the output directory
    outputDir = argv[2] if len(argv) > 2 else downloader.defaultOutputdir

    # If the third argument is set, use that as the number of jobs to list
    numberToList = argv[3] if len(argv) > 3 else downloader.defaultNumberToList

    # If the fourth argument is set, use that as the pid file, otherwise use the default
    pidFile = argv[4] if len(argv) > 4 else "/var/run/bacalhau-downloader-runner.pid"

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
    scheduler.add_job(func=job, trigger="interval", args=[outputDir, numberToList], seconds=secondsBetweenRun)
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
