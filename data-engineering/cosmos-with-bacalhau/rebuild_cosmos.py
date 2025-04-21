#!/usr/bin/env python3
"""
Script to rebuild the CosmosUploader image with the DateTime parsing fixes.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def print_color(message, color=None):
    """Print a colored message."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'reset': '\033[0m',
        'bold': '\033[1m',
    }
    
    if color and color in colors:
        print(f"{colors[color]}{message}{colors['reset']}")
    else:
        print(message)

def main():
    """Main function to rebuild the CosmosUploader image."""
    print_color("Rebuilding CosmosUploader with DateTime parsing fixes", "bold")
    print_color("This will ensure we use the correct image for sensor simulation.", "yellow")
    print()
    
    # Generate a unique tag with current timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    tag = f"fixed-dates-{timestamp}"
    
    print_color(f"Using tag: {tag}", "blue")
    
    # Run the build with the new tag
    try:
        # Check if we're in the right directory
        if not Path("cosmos-uploader").exists():
            print_color("Error: cosmos-uploader directory not found.", "red")
            print_color("Make sure you're running this script from the project root directory.", "red")
            return 1
        
        # Build the image with the new tag
        cmd = ["cd", "cosmos-uploader", "&&", "./build.sh", "--tag", tag]
        print_color(f"Running: {' '.join(cmd)}", "yellow")
        
        # We need to use shell=True here because of the cd command
        process = subprocess.run(
            f"cd cosmos-uploader && ./build.sh --tag {tag}",
            shell=True,
            check=True,
            text=True
        )
        
        print_color("Build successful!", "green")
        print()
        
        # Tag as latest too
        subprocess.run(
            ["docker", "tag", f"cosmos-uploader:{tag}", "cosmos-uploader:latest"],
            check=True,
            text=True
        )
        
        print_color("Image successfully tagged as:", "green")
        print_color(f"  - cosmos-uploader:{tag}", "blue")
        print_color(f"  - cosmos-uploader:latest", "blue")
        print()
        
        # Now clean up any existing containers
        print_color("Cleaning up existing containers...", "yellow")
        cleanup_script = Path("cleanup_containers.py")
        if cleanup_script.exists():
            subprocess.run(["python3", "cleanup_containers.py"], check=False)
        else:
            print_color("Warning: cleanup_containers.py not found, skipping cleanup", "yellow")
        
        print()
        print_color("Rebuild complete!", "green")
        print_color("You can now run ./sensor_manager.py start to start the simulation with the fixed CosmosUploader.", "green")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print_color(f"Error building image: {e}", "red")
        return 1
    except Exception as e:
        print_color(f"Unexpected error: {e}", "red")
        return 1

if __name__ == "__main__":
    sys.exit(main())