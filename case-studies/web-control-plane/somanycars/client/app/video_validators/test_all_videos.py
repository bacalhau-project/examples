#!/usr/bin/env python3

# Using the latest YOLO model, create a known table for every video in the source video directory
# Analyze videos 10 seconds at a time, looking for Cars and Trucks. Create a dict, with the video name as the key
# then a dict with the start of the clip window as a key, and a list of the detected objects as the value

# This script will run on a laptop, and requires no arguments. Just run over every video in the source video directory. 
# Output all the findings do a json file.

import argparse
import datetime
import logging
import os
import random
import signal
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image
from tqdm import tqdm
import torch

import jsonpickle

from ultralytics import YOLO

import json

import supervision as sv

def process_video(video_path: Path) -> dict:
    tracker = sv.ByteTrack()
    if torch.cuda.is_available():
        device_backend = "0"
    elif torch.backends.mps.is_available():
        device_backend = "mps"
    else:
        device_backend = "cpu"

    model = YOLO(Path(__file__).parent / "weights" / "yolov8n.pt")
    # Load the video
    vid = cv2.VideoCapture(str(video_path))
    
    # Get the video name
    video_name = video_path.name
    
    # Create a dict to store the detections
    detections = {}
    
    # Loop through the video - 100 frames at a time

    # Get total frames in the video
    total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))

    checkpointed_detections = {}

    for i in tqdm(range(total_frames)):
        ret, frame = vid.read()
        if not ret:
            break
        
        results = model(
            frame,
            verbose=False,
            conf=0.4,
            iou=0.5,
            device=device_backend,
        )[0]

        detections = sv.Detections.from_ultralytics(results)  # Getting detections
        # Filtering classes for car and truck only instead of all COCO classes.
        # Car == 2
        # Truck == 7
        detections = detections[
            np.where((detections.class_id == 2) | (detections.class_id == 7))
        ]
        detections = tracker.update_with_detections(detections)
        
        if i % 100 == 0:
            checkpointed_detections[str(i)] = jsonpickle.encode(detections)
            tracker = sv.ByteTrack()
            detections = {}
        
    vid.release()
    
    return {video_name: checkpointed_detections}


def main():
    # Get the source video directory
    source_video_directory = Path(__file__).parent / "videos"
    
    # Get the output file
    output_file = Path(__file__).parent / "output.json"
    
    # Get the list of video files
    video_files = list(source_video_directory.glob("*.MOV"))
    
    # Create a dict to store all the detections
    all_detections = {}
    
    # Loop through the video files
    for video_file in video_files:
        print(f"Processing video: {video_file}")
        detections = process_video(video_file)
        all_detections.update(detections)
    
    # Write the detections to the output file
    with open(output_file, "w") as f:
        json.dump(all_detections, f)
        
        
main()