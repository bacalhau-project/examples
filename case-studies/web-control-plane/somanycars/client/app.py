# app.py
import argparse
import asyncio
import os
import random
import signal

import cv2
import numpy as np
import supervision as sv
import uvicorn
import yaml
from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from ultralytics import YOLO
from vidgear.gears.asyncio import WebGear
from vidgear.gears.asyncio.helper import reducer

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


async def run_model(reset=False, frame=None, frame_number=0):
    settings = get_settings()

    # Wait for the model to load the first time
    if settings.model is None:
        reset = True

    if reset:
        settings.checkpoint_total_detections()
        settings.tracker = sv.ByteTrack()
        settings.load_model(YOLO(settings.ml_model_config["source_weights_path"]))

    results = settings.model(
        frame,
        verbose=False,
        conf=settings.ml_model_config["confidence_threshold"],
        iou=settings.ml_model_config["iou_threshold"],
    )[0]

    detections = sv.Detections.from_ultralytics(results)  # Getting detections
    # Filtering classes for car and truck only instead of all COCO classes.
    # Car == 2
    # Truck == 7
    detections = detections[
        np.where((detections.class_id == 2) | (detections.class_id == 7))
    ]
    detections = settings.tracker.update_with_detections(detections)
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


async def track_video(frame, frame_number, reset=False):
    settings = get_settings()
    config_file_path = settings.get_model_config_path()

    if os.path.exists(config_file_path):
        last_update = os.path.getmtime(config_file_path)
        if last_update != settings.config_last_update:
            settings.config_last_update = last_update
            with open(config_file_path, "r") as file:
                settings.ml_model_config = yaml.safe_load(file)

            reset = True

    # Calculate the number of frames processed per clip (based on skip frames)
    settings.frames_processed_per_clip = (
        settings.FPS
        * settings.NUMBER_OF_SECONDS_PER_CLIP
        / settings.ml_model_config["skip_frames"]
    )

    # If the frame_number is not divisible by skip_frames, skip the frame
    if (
        settings.ml_model_config["skip_frames"]
        and settings.ml_model_config["skip_frames"] > 1
    ):
        if frame_number % settings.ml_model_config["skip_frames"] != 0:
            return

    await run_model(reset, frame, frame_number)


async def frames_producer():
    settings = get_settings()

    signal.signal(signal.SIGINT, signal_handler)

    video_file = settings.ml_model_config["source_video_path"]
    stream = cv2.VideoCapture(video_file)
    total_frames = int(stream.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_in_current_clip = random.randint(0, total_frames)
    stream.set(cv2.CAP_PROP_POS_FRAMES, frames_in_current_clip)

    while continue_stream:
        (grabbed, frame) = stream.read()
        frames_in_current_clip += 1

        reset = False

        if (
            not grabbed
            or frames_in_current_clip
            >= settings.NUMBER_OF_SECONDS_PER_CLIP * settings.FPS
        ):
            frames_in_current_clip = 0
            # If not grabbed, assume we're at the end, and start over
            if not grabbed:
                stream.set(cv2.CAP_PROP_POS_FRAMES, frames_in_current_clip)
            (grabbed, frame) = stream.read()
            reset = True

        # Create a task to track the video
        asyncio.create_task(track_video(frame, frames_in_current_clip, reset))

        # reducer frames size if you want more performance otherwise comment this line
        frame = await reducer(frame, percentage=80)  # reduce frame by 30%
        # handle JPEG encoding
        encodedImage = cv2.imencode(".jpg", frame)[1].tobytes()
        # yield frame in byte format
        yield (
            b"--frame\r\nContent-Type:video/jpeg2000\r\n\r\n" + encodedImage + b"\r\n"
        )
        await asyncio.sleep(1.0 / 30.0)
    # close stream
    stream.release()


app = WebGear(logging=True, **options)
templates = Jinja2Templates(directory="templates")
app.config["generator"] = frames_producer
app.config["generator_kwargs"] = {
    "source": "example_video/IMG_9305.MOV",
    "url": "/video",
}
app.middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]
model = None


async def index(request: Request):
    vals = get_json(False)
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
        },
    )


app.routes.append(Route("/", endpoint=index))
app.routes.append(Route("/video", endpoint=app))
app.routes.append(Route("/json", endpoint=json_endpoint))
app.routes.append(Route("/json-testing", endpoint=json_testing))
app.routes.append(Mount("/static", app=StaticFiles(directory="static"), name="static"))
