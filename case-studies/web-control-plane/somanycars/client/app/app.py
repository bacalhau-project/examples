# app.py
import asyncio
import os
import random
import signal

import cv2
import numpy as np
import supervision as sv
import yaml
from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from ultralytics import YOLO
from vidgear.gears.asyncio import WebGear
from vidgear.gears.asyncio.helper import reducer

from pathlib import Path

import datetime
from app_settings import get_settings
from json_functions import get_json, json_endpoint, json_testing

continue_stream = True


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


# various performance tweaks
options = {
    "frame_size_reduction": 40,
    "jpeg_compression_quality": 80,
    "jpeg_compression_fastdct": True,
    "jpeg_compression_fastupsample": False,
    "hflip": True,
    "exposure_mode": "auto",
    "iso": 800,
    "exposure_compensation": 15,
    "awb_mode": "horizon",
    "sensor_mode": 0,
    "skip_generate_webdata": True,
}


def signal_handler(signal, frame):
    global continue_stream
    # This function will be called when SIGINT is received
    print("SIGINT received, shutting down gracefully...")
    continue_stream = False  # Stops the event loop, causing the server to shut down


async def run_model(frame=None, frame_number=0):
    settings = get_settings()

    ml_model_config = settings.get("ml_model_config")

    model = settings.get("model")
    results = model(
        frame,
        verbose=False,
        conf=ml_model_config["confidence_threshold"],
        iou=ml_model_config["iou_threshold"],
    )[0]

    detections = sv.Detections.from_ultralytics(results)  # Getting detections
    # Filtering classes for car and truck only instead of all COCO classes.
    # Car == 2
    # Truck == 7
    detections = detections[
        np.where((detections.class_id == 2) | (detections.class_id == 7))
    ]
    detections = settings.update_tracker_with_detections(detections)
    for index in range(len(detections.class_id)):
        if detections.tracker_id[index] not in settings.working_detections:
            settings.working_detections[int(detections.tracker_id[index])] = Detection(
                confidence=str(round(detections.confidence[index])),
                class_id=int(detections.class_id[index]),
                tracker_id=int(detections.tracker_id[index]),
                frame_number=frame_number,
            )
        else:
            settings.working_detections[detections.tracker_id[index]].increment(
                frame_number
            )


async def track_video(frames):
    settings = get_settings()
    settings.update_tracker(sv.ByteTrack()) # Reset the tracker

    config_file_path = settings.get_model_config_path()
    ml_model_config = settings.get("ml_model_config")

    if os.path.exists(config_file_path):
        last_update = os.path.getmtime(config_file_path)
        if (
            last_update != settings.get("config_last_update")
            or ml_model_config is None
        ):
            # Convert the last update time to a datetime object
            last_update_datetime = datetime.datetime.fromtimestamp(last_update)
            settings.set("config_last_update", last_update_datetime)
            with open(config_file_path, "r") as file:
                ml_model_config = yaml.safe_load(file)
            settings.load_model(YOLO(ml_model_config["source_weights_path"]))
            settings.set("ml_model_config", ml_model_config)

    FPS = settings.get("FPS")
    NUMBER_OF_SECONDS_PER_CLIP = settings.get("NUMBER_OF_SECONDS_PER_CLIP")
    
    # Calculate the number of frames processed per clip (based on skip frames)
    settings.set("frames_processed_per_clip" , (
        FPS
        * NUMBER_OF_SECONDS_PER_CLIP
        / ml_model_config["skip_frames"]
    ))

    for frame_number, frame in enumerate(frames):
        # If the frame_number is not divisible by skip_frames, skip the frame
        if (
            ml_model_config["skip_frames"]
            and ml_model_config["skip_frames"] > 1
        ):
            if frame_number % ml_model_config["skip_frames"] != 0:
                continue

        await run_model(frame, frame_number)

    settings.checkpoint_total_detections()


async def frames_producer():
    settings = get_settings()

    signal.signal(signal.SIGINT, signal_handler)
    ml_model_config = settings.get("ml_model_config")
    NUMBER_OF_SECONDS_PER_CLIP = settings.get("NUMBER_OF_SECONDS_PER_CLIP")
    FPS = settings.get("FPS")

    video_file = ml_model_config["source_video_path"]
    stream = cv2.VideoCapture(video_file)
    total_frames = int(stream.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_in_current_clip = random.randint(0, total_frames)
    stream.set(cv2.CAP_PROP_POS_FRAMES, frames_in_current_clip)

    frames_in_current_clip = 0
    current_clip_frames = []

    while continue_stream:
        (grabbed, frame) = stream.read()
        frames_in_current_clip += 1
        current_clip_frames.append(frame)

        if (
            not grabbed
            or frames_in_current_clip
            >= NUMBER_OF_SECONDS_PER_CLIP * FPS
        ):
            # If not grabbed, assume we're at the end, and start over
            if not grabbed:
                stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
            (grabbed, frame) = stream.read()

            await asyncio.create_task(track_video(current_clip_frames))

            frames_in_current_clip = 0
            current_clip_frames = []
            continue

        # reducer frames size if you want more performance otherwise comment this line
        frame = await reducer(frame, percentage=30)  # reduce frame by 30%
        # handle JPEG encoding
        encodedImage = cv2.imencode(".jpg", frame)[1].tobytes()
        # yield frame in byte format
        yield (
            b"--frame\r\nContent-Type:video/jpeg2000\r\n\r\n" + encodedImage + b"\r\n"
        )
        await asyncio.sleep(1.0 / 30.0)
    # close stream
    stream.release()

origins = ["*"]

app = WebGear(logging=True, **options)
templates = Jinja2Templates(directory="templates")
app.config["generator"] = frames_producer
app.middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
]
model = None


async def index(request: Request):
    vals = get_json(False)
    template_path = str(Path(__file__).parent / "templates" )
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "hostname": vals["hostname"],
            "ip": vals["ip"],
            "model_weights": vals["model_weights"],
            "hashCode": vals["hashCode"],
            "zone": vals["zone"],
            "region": vals["region"],
            "nodeID": vals["nodeID"],
            "video_feed": vals["video_feed"],
            "confidence_threshold": vals["confidence_threshold"],
            "iou_threshold": vals["iou_threshold"],
            "skip_frames": vals["skip_frames"],
            "source_video_path": vals["source_video_path"],
            "total_detections": vals["total_detections"],
            "external_ip": vals["external_ip"],
        },
    )


app.routes.append(Route("/", endpoint=index))
app.routes.append(Route("/video", endpoint=app))
app.routes.append(Route("/json", endpoint=json_endpoint))
app.routes.append(Route("/json-testing", endpoint=json_testing))
app.routes.append(Mount("/static", app=StaticFiles(directory="app/static"), name="static"))
