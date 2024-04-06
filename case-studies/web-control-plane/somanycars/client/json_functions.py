import socket
from pathlib import Path

import jsonpickle
import yaml
from fastapi import Request, Response

from app_settings import get_settings
from node_functions import generate_node, generateHashCode, test_node


async def json_testing(request: Request):
    return json_endpoint(request=request, testing=True)


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
        hostname = socket.gethostname()
        ip = socket.gethostbyname(socket.gethostname())
        node_info = Path("/etc/bacalhau-node-info")
        zone = "N/A"
        region = "N/A"
        external_ip = "localhost"
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

    hashCodeValue = generateHashCode(hostname)
    node_id = f"n-{hashCodeValue}"
    video_feed = f"http://{external_ip}:14041/video"

    # If /data/config.yml exists
    node_config_file = Path("/data/config.yaml")
    if node_config_file.exists():
        with open(node_config_file, "r") as file:
            try:
                node_config = yaml.safe_load(file)
                node = node_config["node"]
                node_id = node["name"]
            except yaml.YAMLError as exc:
                print(f"Could not read node->name: {exc}")
    else:
        print("Could not find /data/config.yaml")

    if settings.ml_model_config.get("source_video_path") is None:
        settings.load_model_config()

    node = generate_node(
        hostname=hostname,
        ip=ip,
        model_weights=settings.ml_model_config["source_weights_path"],
        hashCode=hashCodeValue,
        zone=zone,
        region=region,
        nodeID=node_id,
        video_feed=video_feed,
        confidence_threshold=settings.ml_model_config["confidence_threshold"],
        iou_threshold=settings.ml_model_config["iou_threshold"],
        skip_frames=settings.ml_model_config["skip_frames"],
        source_video_path=settings.ml_model_config["source_video_path"],
        total_detections=settings.total_detections,
        frames_processed_per_clip=settings.frames_processed_per_clip,
        external_ip=external_ip,
    )

    return node
