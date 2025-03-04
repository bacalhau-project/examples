import base64
import os
import sys


def __safe_print(*args, **kwargs):
    sys.__stdout__.write(" ".join(map(str, args)) + "\n")
    sys.__stdout__.flush()


def __exec_script(script, is_b64=False):
    if is_b64:
        try:
            script = base64.b64decode(script).decode("utf-8")
        except Exception as e:
            __safe_print(f"Error decoding base64: {e}")
            return

    try:
        # Use a clean dictionary for globals to avoid conflicts
        globals_dict = {
            "__builtins__": __builtins__,
            "print": __safe_print,  # Provide our safe print function
        }

        exec(script, globals_dict)
    except Exception:
        import traceback

        traceback.print_exc(file=sys.__stdout__)
        sys.__stdout__.flush()


def main():
    script = os.environ.get("SCRIPT", "")
    debug = os.environ.get("DEBUG", "").lower() in ["true", "1"]
    b64 = os.environ.get("B64_ENCODED", "").lower() in ["true", "1"]

    if debug:
        __safe_print("Environment Variables:", os.environ)

    if not script:
        __safe_print("No script to run")
        sys.exit(1)

    if debug:
        __safe_print(f"Executing script:\n{'=' * 80}")

    __exec_script(script, is_b64=b64)


if __name__ == "__main__":
    main()
