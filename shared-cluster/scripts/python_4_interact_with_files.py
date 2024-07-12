# Initial Analysis of files
import argparse
import os
import sys
from datetime import datetime

import h5py
import humanize
import numpy as np
from rich import print
from rich.console import Console
from rich.table import Table


def list_azureshare_directory(directory):
    """
    Print a pretty tree of the azureshare directory with file details.
    """
    max_name_length = 0
    all_entries = []

    def collect_entries(dir_path, prefix=""):
        nonlocal max_name_length
        entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            full_name = f"{prefix}{'└── ' if is_last else '├── '}{entry.name}"
            if entry.is_file():
                size = humanize.naturalsize(entry.stat().st_size, gnu=True)
                date = datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                all_entries.append((full_name, size, date))
                max_name_length = max(max_name_length, len(full_name))
            if entry.is_dir():
                full_name += "/"
                all_entries.append((full_name, "", ""))
                max_name_length = max(max_name_length, len(full_name))
                collect_entries(entry.path, prefix + ("    " if is_last else "│   "))

    collect_entries(directory)

    # Calculate the required console width
    max_size_length = max(len(entry[1]) for entry in all_entries)
    max_date_length = max(len(entry[2]) for entry in all_entries)
    required_width = (
        max_name_length + max_size_length + max_date_length + 4
    )  # 4 for padding

    # Create a console with the required width
    console = Console(width=required_width)

    # Create a table that fits within the console
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Size", style="bold", justify="right")
    table.add_column("Date", style="bold")

    for entry in all_entries:
        table.add_row(*entry)

    # Print the table
    console.print(table)


def print_structure(structure, indent=""):
    if structure["type"] == "Group":
        print(f"{indent}Group:")
        print(f"{indent}  Attributes: {structure['attributes']}")
        for name, child in structure["children"].items():
            print(f"{indent}  {name}:")
            print_structure(child, indent + "    ")
    elif structure["type"] == "Dataset":
        print(f"{indent}Dataset:")
        print(f"{indent}  Shape: {structure['shape']}")
        print(f"{indent}  Dtype: {structure['dtype']}")
        print(f"{indent}  Attributes: {structure['attributes']}")
    else:
        print("Unknown type")


def check_file(file_path):
    if not os.path.exists(file_path):
        return f"File does not exist: {file_path}"
    if not os.access(file_path, os.R_OK):
        return f"File is not readable: {file_path}"
    return None


def dump_attributes(item):
    attr_dict = {}
    for key, value in item.attrs.items():
        if isinstance(value, (np.ndarray, list)):
            attr_dict[key] = value.tolist() if isinstance(value, np.ndarray) else value
        elif isinstance(value, bytes):
            attr_dict[key] = value.decode("utf-8", errors="ignore")
        else:
            attr_dict[key] = value
    return attr_dict


def dump_structure(group, path="/"):
    structure = {"type": "Group", "attributes": dump_attributes(group), "children": {}}

    for key, item in group.items():
        item_path = f"{path}/{key}"
        if isinstance(item, h5py.Group):
            structure["children"][key] = dump_structure(item, item_path)
        elif isinstance(item, h5py.Dataset):
            structure["children"][key] = {
                "type": "Dataset",
                "shape": item.shape,
                "dtype": str(item.dtype),
                "attributes": dump_attributes(item),
            }

    return structure


def analyze_h5_file(file_path):
    file_check = check_file(file_path)
    if file_check:
        return {"Error": file_check}

    try:
        with h5py.File(file_path, "r") as f:
            summary = {"structure": dump_structure(f), "data_analysis": {}}
            explore_group(f, "/", summary["data_analysis"])
        return summary
    except Exception as e:
        import traceback

        return {
            "Error": f"Unable to open or process the file: {str(e)}",
            "Traceback": traceback.format_exc(),
        }


def explore_group(group, path, summary):
    for key, item in group.items():
        item_path = f"{path}/{key}"
        if isinstance(item, h5py.Group):
            summary[item_path] = "Group"
            explore_group(item, item_path, summary)
        elif isinstance(item, h5py.Dataset):
            analyze_dataset(item, item_path, summary)


def analyze_dataset(dataset, path, summary):
    dataset_info = {
        "Type": str(dataset.dtype),
        "Shape": dataset.shape,
        "Size": dataset.size,
        "Compression": dataset.compression,
        "Compression Opts": dataset.compression_opts if dataset.compression else None,
    }

    if dataset.size > 0:
        try:
            if np.issubdtype(dataset.dtype, np.number):
                chunk_size = min(1000, dataset.size)
                sample = dataset[0:chunk_size]  # Use slicing instead of [:]
                dataset_info.update(
                    {
                        "Sample Min": sample.min().item(),
                        "Sample Max": sample.max().item(),
                        "Sample Mean": sample.mean().item(),
                    }
                )
            elif dataset.dtype.char in ["S", "U"]:
                sample_size = min(1000, dataset.size)
                sample = dataset[0:sample_size]  # Use slicing instead of [:]
                unique_values = np.unique(sample)
                dataset_info["Unique Values in Sample"] = len(unique_values)
                if len(unique_values) <= 10:
                    dataset_info["Sample Values"] = [
                        v.decode("utf-8", errors="ignore")
                        if isinstance(v, bytes)
                        else v
                        for v in unique_values.tolist()
                    ]
        except Exception:
            pass
            # dataset_info["Error"] = f"Unable to read data: {str(e)}"

    summary[path] = dataset_info


def print_summary(summary):
    print("\nFile Structure:")
    print_structure(summary.get("structure", {}))

    print("\nData Analysis:")
    data_analysis = summary.get("data_analysis", {})
    if isinstance(data_analysis, dict):
        for path, info in data_analysis.items():
            print(f"\nPath: {path}")
            if isinstance(info, str):
                print(info)
            elif isinstance(info, dict):
                for key, value in info.items():
                    print(f"  {key}: {value}")
            else:
                print(f"Unexpected type for info: {type(info)}")
    else:
        print(data_analysis)


# Set HDF5_PLUGIN_PATH to an empty string
os.environ["HDF5_PLUGIN_PATH"] = ""


def main():
    # Parse environment variables and make them the default
    action = os.environ.get("ACTION", "list")
    directory = os.environ.get("DIRECTORY", "/azureshare")
    file_path = os.environ.get("FILE_PATH", None)

    parser = argparse.ArgumentParser(
        description="Analyze HDF5 files or list azureshare directory."
    )
    parser.add_argument(
        "-a",
        "--analyze_file",
        help="Path to the HDF5 file to analyze",
        default=file_path,
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List contents of azureshare directory",
    )
    parser.add_argument(
        "-d",
        "--directory",
        default=directory,
        help="Directory to analyze, defaults to /azureshare",
    )
    args = parser.parse_args()

    if args.list:
        action = "list"
    elif args.analyze_file:
        action = "analyze_file"

    print(f"h5py version: {h5py.__version__}")
    print("h5py info:")
    config = h5py.get_config()
    print(f"  HDF5 version: {h5py.version.hdf5_version}")
    print(f"  MPI enabled: {config.mpi}")
    print(f"  ROS3 enabled: {config.ros3}")
    print(f"  Direct VFD enabled: {config.direct_vfd}")
    print(f"File path: {os.environ.get('FILE_PATH')}")

    if action == "list":
        azureshare_dir = args.directory
        list_azureshare_directory(azureshare_dir)
    elif action == "analyze_file":
        if not os.path.exists(args.analyze_file):
            print(f"File not found: {args.analyze_file}")
            sys.exit(1)

        with h5py.File(args.analyze_file, "r") as f:
            results = analyze_h5_file(f)
            print_summary(results)
    else:
        print(f"Unknown action: {action}")
        parser.print_help()


if __name__ == "__main__":
    main()
