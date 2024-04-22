#!/usr/bin/env python

# Load json file from output.json
# Pretty print first the key for *.MOV then, indent and show every detection by frame

import json
from pprint import pprint

from pathlib import Path

import jsonpickle

with open(Path(__file__).parent / 'output.json') as f:
    data = json.load(f)

    for file_name, frames in data.items():
        print(f"File: {file_name}")
        for frame_count, frame_data in frames.items():
            decoded = jsonpickle.decode(frame_data)
            window_pairs = len(decoded.tracker_id)
            print(f"Frame count: {frame_count}")
            for j in range(len(decoded.tracker_id)):
                print(f"Tracker ID: {decoded.tracker_id[j]}, Class ID: {decoded.class_id[j]}")

            print(f"Total for this window: {window_pairs}")
            print("-----")
        
# Output: 
# 2020-02-10_10-00-00.MOV
# {
#     "0": "[{\"class_id\": 2, \"confidence\": 0.999, \"bbox\": [0.0, 0.0, 0.0, 0.0]}]",
#     "100": "[{\"class_id\": 2, \"
#     ...
#     ...