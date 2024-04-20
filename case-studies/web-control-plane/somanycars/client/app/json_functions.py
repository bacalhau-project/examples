import socket
from pathlib import Path

import jsonpickle
import yaml
from fastapi import Request, Response
from jsonschema import validate, ValidationError
import json

import logging
import datetime

import videoApp
import signal

from video_app_settings import get_settings
from node_functions import generate_node, generateHashCode, test_node
logger = logging.getLogger(__name__)

def validate_json(json_object: dict) -> (bool, str):
    try:
        validate(instance=json_object, schema=load_json_schema())
    except ValidationError as e:
        logger.error(f"JSON is not valid: {e}")
        return False, str(e)
    return True, ""


async def json_endpoint(request: Request, testing=False):
    node = get_json(testing=testing)
    return Response(content=jsonpickle.dumps(node), media_type="application/json")


def get_json(testing=False):
    settings = get_settings()
    if testing:
        testNode = test_node()
        ip = testNode["ip"]
        hostname = testNode["hostname"]
        zone = testNode["zone"]
        region = testNode["region"]
        external_ip = testNode["external_ip"]
    else:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except Exception as e:
            logger.error(f"Could not get hostname and ip: {e}")
            hostname = "localhost"
            ip = "127.0.0.1"
        
    node_info = Path("/app/config/bacalhau-node-info")
    zone = "N/A"
    region = "N/A"
    external_ip = "localhost"
    logger.debug(f"Checking if {node_info} exists")
    if node_info.exists():
        # Read from /etc/bacalhau-node-info and get ZONE= and REGION=
        with open(node_info, "r") as file:
            lines = file.readlines()
            for line in lines:
                if "ZONE=" in line:
                    zone = line.split("=")[1].replace("\n", "")
                if "REGION=" in line:
                    region = line.split("=")[1].replace("\n", "")
                if "EXTERNAL_IP=" in line:
                    external_ip = line.split("=")[1].replace("\n", "")
                if "PRIVATE_IP=" in line:
                    private_ip = line.split("=")[1].replace("\n", "")
                    if private_ip != ip:
                        ip = private_ip

    hashCodeValue = generateHashCode(hostname)
    node_id = f"n-{hashCodeValue}"
    video_feed = f"http://{external_ip}:14041/video"

    node_config_file = settings.get("node_config_path")
    if node_config_file.exists():
        with open(node_config_file, "r") as file:
            try:
                node_config = yaml.safe_load(file)
                node = node_config["node"]
                node_id = node["name"]
            except yaml.YAMLError as exc:
                logger.warn(f"Could not read node->name: {exc}")
    else:
        logger.debug(f"Could not find {node_config_file}")

    ml_model_config = settings.get("ml_model_config")
    if ml_model_config.get("source_video_path") is None:
        ml_model_config = settings.load_model_config()

    # last_inference_time and config_last_update are stored as datetime objects, so we need to convert them to strings
    last_inference_time = settings.get("last_inference_time")
    last_config_update = settings.get("config_last_update")
    if last_inference_time is not None and isinstance(last_inference_time, datetime.datetime):
        last_inference_time = last_inference_time.isoformat()
    if last_config_update is not None and isinstance(last_config_update, datetime.datetime):
        last_config_update = last_config_update.isoformat()
        
    model_running = settings.is_model_running()
    if model_running is not None and isinstance(model_running, datetime.datetime):
        model_running = model_running.isoformat()
    else:
        # If the model is not running, we should set the value to minimum datetime
        model_running = datetime.datetime.min.isoformat()
    
    node = generate_node(
        hostname=hostname,
        ip=ip,
        model_weights=ml_model_config["source_weights_path"],
        hashCode=hashCodeValue,
        zone=zone,
        region=region,
        nodeID=node_id,
        video_feed=video_feed,
        confidence_threshold=ml_model_config["confidence_threshold"],
        iou_threshold=ml_model_config["iou_threshold"],
        skip_frames=ml_model_config["skip_frames"],
        source_video_path=ml_model_config["source_video_path"],
        total_detections=settings.get("total_detections"),
        frames_processed_per_clip=settings.get("frames_processed_per_clip"),
        external_ip=external_ip,
        last_inference_time=last_inference_time,
        config_last_update=last_config_update,
        model_running=model_running,
        stopping=not settings.get_continue_stream(),
    )
    
    valid, err = validate_json(node)
    
    if not valid:
        logger.error(f"JSON is not valid: {err}")
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    return node

def load_json_schema():
    schema_path = Path(__file__).parent / "schema" / "feed_schema.json"
    schema = schema_path.read_text()
    return json.loads(schema)

