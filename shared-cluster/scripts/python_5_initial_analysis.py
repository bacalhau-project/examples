import os
import sys

import h5py
import numpy as np
from rich import print


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


def analyze_h5_file(file_or_path):
    if isinstance(file_or_path, str):
        file_check = check_file(file_or_path)
        if file_check:
            return {"Error": file_check}
        file_obj = h5py.File(file_or_path, "r")
    elif isinstance(file_or_path, h5py.File):
        file_obj = file_or_path
    else:
        return {"Error": "Invalid input: expected file path or h5py.File object"}

    try:
        summary = {"structure": dump_structure(file_obj), "data_analysis": {}}
        explore_group(file_obj, "/", summary["data_analysis"])
        return summary
    except Exception as e:
        import traceback

        return {
            "Error": f"Unable to process the file: {str(e)}",
            "Traceback": traceback.format_exc(),
        }
    finally:
        if isinstance(file_or_path, str):
            file_obj.close()


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
                sample = dataset[0:chunk_size]
                dataset_info.update(
                    {
                        "Sample Min": sample.min().item(),
                        "Sample Max": sample.max().item(),
                        "Sample Mean": sample.mean().item(),
                    }
                )
            elif dataset.dtype.char in ["S", "U"]:
                sample_size = min(1000, dataset.size)
                sample = dataset[0:sample_size]
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


def main():
    os.environ["HDF5_PLUGIN_PATH"] = ""
    file_path = os.environ.get("FILE_PATH")

    if not file_path:
        print("Error: FILE_PATH environment variable is not set.")
        sys.exit(1)

    print(f"h5py version: {h5py.__version__}")
    print("h5py info:")
    config = h5py.get_config()
    print(f"  HDF5 version: {h5py.version.hdf5_version}")
    print(f"  MPI enabled: {config.mpi}")
    print(f"  ROS3 enabled: {config.ros3}")
    print(f"  Direct VFD enabled: {config.direct_vfd}")
    print(f"File path: {file_path}")

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    results = analyze_h5_file(file_path)
    print_summary(results)


if __name__ == "__main__":
    main()
