import os
import re
import subprocess
import sys
from pathlib import Path

import tomli
import tomli_w


def merge_requirements_to_pyproject():
    """Merge requirements.txt into existing pyproject.toml if it exists."""
    current_dir = Path.cwd()
    pyproject_path = current_dir / "pyproject.toml"
    req_path = current_dir / "requirements.txt"

    # Read existing pyproject.toml
    if not pyproject_path.exists():
        print("Error: No pyproject.toml found in current directory")
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)
    
    # Ensure project section exists
    if "project" not in pyproject:
        pyproject["project"] = {}
    if "dependencies" not in pyproject["project"]:
        pyproject["project"]["dependencies"] = []

    # Add requirements.txt packages if they exist
    if req_path.exists():
        print("Found requirements.txt, merging into pyproject.toml...")
        with open(req_path) as f:
            requirements = [line.strip() for line in f 
                          if line.strip() and not line.startswith('#')]
        
        # Merge requirements into existing dependencies
        existing_deps = set(pyproject["project"]["dependencies"])
        existing_deps.update(requirements)
        pyproject["project"]["dependencies"] = sorted(list(existing_deps))
        
        # Remove requirements.txt
        req_path.unlink()
        print("Removed requirements.txt")

    # Ensure UV configuration exists
    if "tool" not in pyproject:
        pyproject["tool"] = {}
    if "uv" not in pyproject["tool"]:
        pyproject["tool"]["uv"] = {
            "venv": ".venv",
            "project-root": ".",
            "pip-tools-compatible": True,
            "editable": True,
            "pip-config": {"no-deps": False, "no-cache-dir": False},
            "resolution": {"allow-prereleases": False, "sources": ["pypi"]}
        }

    # Write updated pyproject.toml
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)
    print("Updated pyproject.toml")

def setup_venv():
    """Create and activate a virtual environment."""
    venv_path = Path.cwd() / ".venv"
    print(f"Creating virtual environment at: {venv_path}")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    return venv_path

def get_venv_python(venv_path):
    """Get the path to the Python interpreter in the venv."""
    if sys.platform == "win32":
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"
    return python_path

def upgrade_all_packages(venv_path):
    """Upgrade all packages in pyproject.toml to their latest versions."""
    python_path = get_venv_python(venv_path)
    if not python_path.exists():
        raise FileNotFoundError(f"Python interpreter not found at {python_path}")
    print(f"Using Python interpreter: {python_path}")
    
    # Set up environment for UV
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_path)
    env["PROJECT_ROOT"] = str(Path.cwd())
    
    try:
        print("Upgrading all packages to latest versions...")
        # Install packages from pyproject.toml first
        subprocess.check_call(["uv", "pip", "install", 
                             "--python", str(python_path),
                             "--upgrade", "."],
                            env=env)
        
        # Get updated package versions
        result = subprocess.run(["uv", "pip", "freeze",
                               "--python", str(python_path)],
                              capture_output=True, text=True,
                              env=env)
        
        # Update pyproject.toml with new versions
        with open("pyproject.toml", "rb") as f:
            pyproject = tomli.load(f)
        
        # Get current dependencies that aren't the local package
        current_deps = set()
        if "dependencies" in pyproject["project"]:
            current_deps = {dep for dep in pyproject["project"]["dependencies"]
                          if not dep.startswith("duckdb-logs-processing")}
        
        # Get updated versions from pip freeze
        updated_deps = set()
        for line in result.stdout.splitlines():
            if line.strip() and not line.startswith('#'):
                pkg = line.strip()
                if not pkg.startswith("duckdb-logs-processing"):
                    updated_deps.add(pkg)
        
        # Combine dependencies, keeping the local package reference
        all_deps = sorted(list(updated_deps))
        if "dependencies" in pyproject["project"]:
            local_pkg = [dep for dep in pyproject["project"]["dependencies"]
                        if dep.startswith("duckdb-logs-processing")]
            if local_pkg:
                all_deps.extend(local_pkg)
        
        pyproject["project"]["dependencies"] = all_deps
        
        with open("pyproject.toml", "wb") as f:
            tomli_w.dump(pyproject, f)
            
        print("Updated pyproject.toml with latest package versions")
        
    except subprocess.CalledProcessError as e:
        print(f"Error upgrading packages: {e}")
        raise

def main():
    # Get absolute path to script directory
    script_dir = Path(__file__).resolve().parent
    print(f"Script directory: {script_dir}")
    
    # Change to script directory
    os.chdir(script_dir)
    print(f"Changed working directory to: {Path.cwd()}")
    
    print("Setting up project...")
    merge_requirements_to_pyproject()
    venv_path = setup_venv()
    
    try:
        upgrade_all_packages(venv_path)
        print("\nAll packages upgraded successfully!")
    except Exception as e:
        print("\nError upgrading packages:", e)
        print("\nYou may need to:")
        print("1. Fix permissions: sudo chown -R $USER ~/Library/Caches/uv")
        print("2. Clear the UV cache: rm -rf ~/Library/Caches/uv")
        print("3. Try running the script again")
        sys.exit(1)

if __name__ == "__main__":
    main()