import os
import sys

# Run command set in COMMAND env variable
command = os.environ["COMMAND"]

if command:
    # Split the command into lines
    command_lines = command.split("\n")

    # Check if the first line is a comment
    if command_lines[0].strip().startswith("#"):
        print("\n" + command_lines[0].strip())

    print("---" * 20 + "\n")
else:
    print("No command to run")
    sys.exit(1)


exec(command)
