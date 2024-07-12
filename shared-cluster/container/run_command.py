import base64
import datetime
import os
import sys

# Run command set in COMMAND env variable
command = os.environ.get("COMMAND", "")
debug = os.environ.get("DEBUG", "")
b64 = os.environ.get("B64_ENCODED", False)

# Print env
if debug:
    print(os.environ)

if command:
    # Split the command into lines
    command_lines = command.split("\n")

    # Check if the first line is a comment
    if command_lines[0].strip().startswith("#"):
        print("\n" + command_lines[0].strip())
    else:
        print(f"\n Running - No Comment at Header - {datetime.datetime.now()}")

    print("---" * 20 + "\n")
else:
    print("No command to run")
    sys.exit(1)

if debug:
    print("Executing...")
    print(f"Full Command: \n{debug}")
    print("=" * 80)

if b64:
    try:
        if debug:
            print("Decoding command:")
            print(command)
            print("=" * 80)
        decoded_command = base64.b64decode(command).decode("utf-8")
        if debug:
            print("Decoded command:")
            print(decoded_command)
            print("=" * 80)
        try:
            if debug:
                print("Executing command:")
                print("=" * 80)
            exec(decoded_command)
        except Exception:
            import traceback

            traceback.print_exc()
    except Exception as e:
        print(f"Error decoding base64: {e}", file=sys.stderr)
else:
    exec(command)
