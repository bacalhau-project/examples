import argparse
import os

import numpy as np
import requests
import supervision as sv
import yaml
from tqdm import tqdm
from ultralytics import YOLO

tracker = sv.ByteTrack()
box_annotator = sv.BoundingBoxAnnotator()


class Config:
    def __init__(self):
        self.source_weights_path = "yolov5s.pt"
        self.confidence_threshold = 0.3
        self.iou_threshold = 0.7
        self.skip_frames = 1
        self.show_progress = True

    def merge_from_yaml(self, path: str) -> None:
        with open(path, "r") as file:
            data = yaml.safe_load(file)
        for key, value in data.items():
            setattr(self, key, value)


class Detection:
    def __init__(self, confidence, class_id, tracker_id, frame_number):
        self.confidence = confidence
        self.class_id = class_id
        self.tracker_id = tracker_id
        self.count = 1
        self.first_frame = frame_number
        self.last_frame = frame_number

    def increment(self, frame_number):
        self.count += 1
        self.last_frame = frame_number


def process_video(
    config: Config,
) -> None:
    if not os.path.exists(config.source_weights_path):
        print(f"File {config.source_weights_path} does not exist")
        print(f"Downloading weights from {config.source_weights_url}")

        with requests.get(config.source_weights_url, stream=True) as r:
            r.raise_for_status()
            with open("large_file.zip", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
    else:
        print(f"Using weights from {config.source_weights_path}")

    model = YOLO(config.source_weights_path)  # Load YOLO model

    tracker = sv.ByteTrack()

    total_frames = 1000
    frame_generator = sv.get_video_frames_generator(
        source_path=config.source_video_path,
        end=total_frames,
    )

    total_detections = {}

    if config.show_progress:
        enumerated_frame_generator = enumerate(
            tqdm(frame_generator, total=total_frames)
        )
    else:
        enumerated_frame_generator = enumerate(frame_generator)

    # with sv.VideoSink(target_path=target_video_path, video_info=video_info) as sink:
    for i, frame in enumerated_frame_generator:
        if config.skip_frames > 1:
            if i % config.skip_frames != 0:
                continue

        # Getting result from model
        results = model(
            frame,
            verbose=False,
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
        )[0]
        detections = sv.Detections.from_ultralytics(results)  # Getting detections
        # Filtering classes for car and truck only instead of all COCO classes.
        # Car == 2
        # Truck == 7
        detections = detections[
            np.where((detections.class_id == 2) | (detections.class_id == 7))
        ]
        detections = tracker.update_with_detections(detections)
        for index in range(len(detections.class_id)):
            if detections.tracker_id[index] not in total_detections:
                total_detections[detections.tracker_id[index]] = Detection(
                    confidence=str(round(detections.confidence[index])),
                    class_id=detections.class_id[index],
                    tracker_id=detections.tracker_id[index],
                    frame_number=i,
                )
            else:
                total_detections[detections.tracker_id[index]].increment(i)


if __name__ == "__main__":
    config = Config()

    parser = argparse.ArgumentParser("video processing with YOLO and ByteTrack")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to the config file"
    )

    if os.path.exists("config.yaml"):
        config.merge_from_yaml("config.yaml")

    parser.add_argument(
        "--source_weights_path",
        required=False,
        help="Path to the source weights file",
        type=str,
    )
    parser.add_argument(
        "--source_video_path",
        required=False,
        help="Path to the source video file",
        type=str,
    )
    parser.add_argument(
        "--target_video_path",
        required=False,
        help="Path to the target video file",
        type=str,
    )
    parser.add_argument(
        "--confidence_threshold",
        default=0.3,
        help="Confidence threshold for the model",
        type=float,
    )
    parser.add_argument(
        "--iou_threshold", default=0.7, help="Iou threshold for the model", type=float
    )

    parser.add_argument(
        "--skip_frames", default=1, help="Only process every n-th frame", type=int
    )
    args = parser.parse_args()

    if not args.args:  # args priority is higher than yaml
        opt = vars(args)
        args = yaml.load(open(args.config), Loader=yaml.FullLoader)
        opt.update(args)
        args = opt
    else:  # yaml priority is higher than args
        opt = yaml.load(open(args.config), Loader=yaml.FullLoader)
        opt.update(vars(args))
        args = opt

    process_video(config)
