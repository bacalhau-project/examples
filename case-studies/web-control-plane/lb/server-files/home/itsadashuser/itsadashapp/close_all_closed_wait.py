#!/usr/bin/env python

import subprocess


def kill_processes_in_close_wait():
    try:
        # Running lsof command to find processes with sockets in CLOSE_WAIT state
        command = "lsof -i | grep CLOSE_WAIT"
        result = subprocess.check_output(command, shell=True, text=True)
        lines = result.strip().split("\n")

        killed_pids = set()

        for line in lines:
            parts = line.split()
            pid = parts[1]  # Process ID
            if pid not in killed_pids:  # Avoid killing the same PID multiple times
                subprocess.run(["kill", "-9", pid], check=True)
                killed_pids.add(pid)
                print(f"Killed process with PID {pid}.")

        if not killed_pids:
            print("No processes in CLOSE_WAIT state found.")

    except subprocess.CalledProcessError as e:
        print("Failed to find or kill processes:", e)


# Run the function
kill_processes_in_close_wait()
