import os
import sys

import h5py
import numpy as np

print(f"Python version: {sys.version}")
print(f"NumPy version: {np.__version__}")
print(f"h5py version: {h5py.__version__}")
print(f"h5py info:\n{h5py.get_config()}")
print(f"File path: {os.environ.get('FILE_PATH')}")
print(f"HDF5_PLUGIN_PATH: {os.environ.get('HDF5_PLUGIN_PATH')}")


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

    try:
        filters = dataset.id.get_create_plist().get_filters()
        dataset_info["Filters"] = [f[0] for f in filters] if filters else None
    except Exception as e:
        dataset_info["Filters Error"] = str(e)

    if dataset.size > 0:
        try:
            if np.issubdtype(dataset.dtype, np.number):
                chunk_size = 1000
                samples = []
                for i in range(0, min(10000, dataset.size), chunk_size):
                    try:
                        sample = dataset[i : i + chunk_size]
                        samples.append(sample)
                    except Exception as e:
                        dataset_info[f"Error reading chunk {i}"] = str(e)
                if samples:
                    combined_sample = np.concatenate(samples)
                    dataset_info.update(
                        {
                            "Sample Min": combined_sample.min(),
                            "Sample Max": combined_sample.max(),
                            "Sample Mean": combined_sample.mean(),
                        }
                    )
            elif dataset.dtype.char in ["S", "U"]:
                sample_size = min(1000, dataset.size)
                sample = dataset[0:sample_size]
                unique_values = np.unique(sample)
                dataset_info["Unique Values in Sample"] = len(unique_values)
                if len(unique_values) <= 10:
                    dataset_info["Sample Values"] = unique_values.tolist()
        except Exception as e:
            dataset_info["Error"] = f"Unable to read data: {str(e)}"

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


# Set HDF5_PLUGIN_PATH to an empty string
os.environ["HDF5_PLUGIN_PATH"] = ""

# Usage
file_path = os.environ.get("FILE_PATH")
if not file_path:
    print("Please set the FILE_PATH environment variable.")
else:
    result = analyze_h5_file(file_path)
    print_summary(result)
