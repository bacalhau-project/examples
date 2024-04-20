# app.py
import logging
import asyncio
import os
import random
import signal
import json_functions 

import logging as log
import torch

import cv2
import numpy as np
import supervision as sv
import yaml, time
from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse, Response

from starlette.staticfiles import StaticFiles
from ultralytics import YOLO
from vidgear.gears.asyncio import WebGear
from vidgear.gears.asyncio.helper import reducer

from functools import lru_cache

from concurrent.futures import ProcessPoolExecutor

from pathlib import Path

import logging

import datetime
from video_app_settings import get_settings
from json_functions import get_json, json_endpoint, load_json_schema, validate_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = True
templates = Jinja2Templates(directory="templates")
executor = ProcessPoolExecutor(max_workers=2)
model_timeout_minutes = 1

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

def run_model(model, frames):
    settings = get_settings()
    logger = logging.getLogger(__name__)
    # If logger doesn't already have stream handler, add one
    if not logger.hasHandlers():
        logger.addHandler(logging.StreamHandler())
    
    time_model_started = settings.get("model_running")
    if time_model_started is not None and time_model_started > datetime.datetime.min:
        logger.debug(f"Model already running at {time_model_started}")
        if time_model_started < datetime.datetime.now() - datetime.timedelta(minutes=model_timeout_minutes):
            logger.debug("Model already running, but it's been running for too long. Stopping it.")
            settings.set_model_stopped()
        else:
            logger.debug("Model already running, skipping.")
            return
    
    logger.debug(f"Model not running, starting it now.")

    logger.debug(f"Starting model - {datetime.datetime.now()}")
    settings.set_model_running(datetime.datetime.now())

    ml_model_config = settings.get("ml_model_config")
    
    if torch.cuda.is_available():
        device_backend = "0"
    elif torch.backends.mps.is_available():
        device_backend = "mps"
    else:
        device_backend = "cpu"

    logger.info(f"Using {device_backend} device backend.")

    for frame_number, frame in enumerate(frames):
        # If the frame_number is not divisible by skip_frames, skip the frame
        if (
            ml_model_config["skip_frames"]
            and ml_model_config["skip_frames"] > 1
        ):
            if frame_number % ml_model_config["skip_frames"] != 0:
                continue
            
            logger.debug(f"Processing frame {frame_number} - Using {device_backend} device backend.")
            start_time = time.time()
            
            results = model(
                frame,
                verbose=False,
                conf=ml_model_config["confidence_threshold"],
                iou=ml_model_config["iou_threshold"],
                device=device_backend,
            )[0]

            detections = sv.Detections.from_ultralytics(results)  # Getting detections
            # Filtering classes for car and truck only instead of all COCO classes.
            # Car == 2
            # Truck == 7
            detections = detections[
                np.where((detections.class_id == 2) | (detections.class_id == 7))
            ]
            detections = settings.update_tracker_with_detections(detections)
            end_time = time.time()
            logger.debug(f"Frame {frame_number} took {end_time - start_time} seconds to process.")
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

            
    settings.checkpoint_total_detections()
    settings.set_model_stopped()

def track_video(frames):
    settings = get_settings()
    logger.info(f"Starting tracking video - {format(datetime.datetime.now())}")
    settings.update_tracker(sv.ByteTrack()) # Reset the tracker

    config_file_path = settings.get_model_config_path()
    ml_model_config = settings.get("ml_model_config")

    reload_model = False

    if os.path.exists(config_file_path):
        last_update = os.path.getmtime(config_file_path)
        try:
            last_update_datetime = datetime.datetime.fromtimestamp(last_update)
        except:
            last_update_datetime = None
        
        if (
            last_update_datetime > settings.get("config_last_update")
            or ml_model_config is None
        ):
            logger.info(f"Last Update Date {last_update_datetime} > {settings.get('config_last_update')} (or model config is None {ml_model_config == None}) -- Reloading model config")
            settings.set("config_last_update", last_update_datetime)
            with open(config_file_path, "r") as file:
                ml_model_config = yaml.safe_load(file)
            
            source_weights_path = ml_model_config["source_weights_path"]
            # If source weights path does not contain a /, assume it's not absolute, and prefix it with the absolute path
            if not Path(source_weights_path).exists() and "/" not in source_weights_path:
                source_weights_path = Path(__file__).parent / source_weights_path
            
            if not Path(source_weights_path).exists():
                logger.error(f"Model weights not found at {source_weights_path}")
                logger.error("Exiting due to missing model weights")
                settings.stop_stream()
                return
            reload_model = True
        
    if settings.get("model") is None or reload_model:
        logger.info(f"No value for model (or reload model == {reload_model==True}) -- Loading model {ml_model_config['source_weights_path']}")
        settings.load_model(YOLO(ml_model_config["source_weights_path"]))
        settings.set("ml_model_config", ml_model_config)

    FPS = settings.get("FPS")
    number_of_seconds_per_clip = ml_model_config["number_of_seconds_per_clip"]
    
    # Calculate the number of frames processed per clip (based on skip frames)
    settings.set("frames_processed_per_clip" , (
        FPS
        * number_of_seconds_per_clip
        / ml_model_config["skip_frames"]
    ))
    
    model = settings.get("model")
    if model is None:
        logger.warn("Model not loaded, skipping tracking")
    else:
        run_model(model, frames)
        
    logger.info(f"Finished tracking video - {format(datetime.datetime.now())}")
    return

async def frames_producer():
    settings = get_settings()
    
    # There shouldn't be a case where the model is already running, so turn it off no matter what.
    settings.set_model_stopped()

    ml_model_config = settings.get("ml_model_config")
    if ml_model_config["source_video_path"] is None:
        logger.info("No video file found - reloading model config")
        settings.load_model_config()
        ml_model_config = settings.get("ml_model_config")
        
    number_of_seconds_per_clip = ml_model_config["number_of_seconds_per_clip"]  
    FPS = settings.get("FPS")

    video_file = ml_model_config["source_video_path"]
    stream = cv2.VideoCapture(video_file)
    total_frames = int(stream.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_in_current_clip = random.randint(0, total_frames)
    stream.set(cv2.CAP_PROP_POS_FRAMES, frames_in_current_clip)

    frames_in_current_clip = 0
    current_clip_frames = []

    while settings.get_continue_stream():
        (grabbed, frame) = stream.read()
        frames_in_current_clip += 1
        # logger.debug(f"Frames in current clip: {frames_in_current_clip}")
        current_clip_frames.append(frame)

        if (
            not grabbed
            or frames_in_current_clip
            >= number_of_seconds_per_clip * FPS
        ):
            # If not grabbed, assume we're at the end, and start over
            if not grabbed:
                logger.debug("Not grabbed, setting position to 0")
                stream.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # Atomically execute the following code - ensure it only executes once. Don't block the thread
            # just skip over it if it's already running.
            
            logger.debug(f"Checking if model is already running - {format(datetime.datetime.now())}")
            if settings.get("model_running") is None or settings.get("model_running") == datetime.datetime.min:
                logger.debug(f"Locking model running submission - {format(datetime.datetime.now())}")
                logger.info("Starting background task to track video.")
                logger.debug(f"Frames in current clip: {frames_in_current_clip}")
                start_time = time.time()
                logger.debug(f"Starting submitting tracking - {format(datetime.datetime.now())}")
                executor.submit(track_video, current_clip_frames)
                end_time = time.time()
                logger.debug(f"Submitting tracking took {end_time - start_time} seconds.")
                logger.debug(f"Unlocking model running submission - {format(datetime.datetime.now())}")
            else:
                logger.info("Model is already running, skipping.")


            frames_in_current_clip = 0
            current_clip_frames = []
            (grabbed, frame) = stream.read()
            continue

        # reducer frames size if you want more performance otherwise comment this line
        frame = await reducer(frame, percentage=80)  # reduce frame by 80%
        
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

@lru_cache()
def get_webgear():
    return WebGear(logging=False, **options, log_level=logging.INFO)

@lru_cache()
def get_app():
    app = get_webgear()
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
    app.routes.append(Route("/", endpoint=index))
    app.routes.append(Route("/ok", endpoint=ok_endpoint))
    app.routes.append(Route("/video", endpoint=app))
    app.routes.append(Route("/json", endpoint=json_endpoint))
    app.routes.append(Mount("/static", app=StaticFiles(directory="static"), name="static"))
    app.routes.append(Route("/schema", endpoint=schema_endpoint))
    
    return app

async def shutdown():
    logger.info("Received shutdown. Shutting down gracefully...")
    app = get_app()
    settings = get_settings()    

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()
    settings.stop_stream()
    app.shutdown()

async def index(request: Request):
    vals = get_json(False)
    logger.debug(f"vals: {vals}")
    template_path = str(Path(__file__).parent / "templates" )
    
    contextObj = {
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
        "model_running": vals["model_running"] if vals["model_running"] is not None else False,
        "frames_processed_per_clip": vals["frames_processed_per_clip"],
        "last_inference_time": vals["last_inference_time"],
        "config_last_update": vals["config_last_update"],
        "stopping": vals["stopping"],
    }
    valid, err = validate_json(contextObj)
    if(valid):
        return templates.TemplateResponse("app.html", {"request": request, "context": contextObj, "errorText": ""})
    else:
        return templates.TemplateResponse("app.html", {"request": request, "context": contextObj, "errorText": "Invalid JSON: " + err})

async def ok_endpoint(request):
    return JSONResponse({"status": "healthy"}, status_code=200)

async def schema_endpoint(request):
    schema = load_json_schema()
    return JSONResponse(schema, status_code=200, media_type="application/schema+json")
