import os
import sys
from pathlib import Path 

from colour import Color

from os import walk


def check_color(color):
    try:
        # Converting 'deep sky blue' to 'deepskyblue'
        color = color.replace(" ", "")
        Color(color)
        # if everything goes fine then return True
        return True
    except ValueError:  # The color code was not found
        return False


def edit_color(color_file, color):
    # Double check to make sure color_file exists
    if not os.path.exists(color_file):
        print("color.txt file not found. (Should never get here - unit test only.)")
        sys.exit(1)

    with open(color_file, "w") as f:
        f.write(f"{color}\n")


if __name__ == "__main__":
    color = os.getenv("COLOR")
    if not color or color == "":
        print("COLOR environment variable not set.")
        exit(1)

    # Test to make sure it's a valid hex color
    if not check_color(color):
        print(
            "Invalid color format. Must be a valid color name or a hex color of the form #FFFFFF to #000000."
        )
        exit(1)

    color_file = os.getenv("COLOR_FILE")
    if not color_file or color_file == "":
        print("COLOR_FILE environment variable not set.")
        exit(1)

    # Check to make sure the color.txt file exists
    if not os.path.exists(color_file):
        print(
            f"""{color_file} file not found at the specified path.
            Current path: {os.getcwd()}.
            All files in the current directory are: {os.listdir()}"""
        )
        
        if os.getenv("TEST_DIRECTORY"):
            dir = os.getenv("TEST_DIRECTORY", "/tmp")
            d = []
            f = []
            for (dirpath, dirnames, filenames) in walk(dir):
                f.extend(filenames)
                d.extend(dirnames)
                break
            print (f"All directories in {dir} are: ", d)
            print (f"All files in {dir} are: ", f)
        
            print ("Full walk:")
            for path, subdirs, files in os.walk(dir):
                for filename in files:
                    print(os.path.join(path, filename))
        

        exit(1)

    edit_color(color_file, color)
    
    # Read the file to make sure it was updated
    with open(color_file, "r") as f:
        read_color = f.readline().strip()
    print(f"Color file {color_file} updated to {read_color}.")
