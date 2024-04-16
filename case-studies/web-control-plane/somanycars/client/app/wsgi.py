import argparse
import asyncio
import cProfile
import io
import os
import pstats
import signal

import yaml
from uvicorn import Config, Server
import uvicorn
import logging

from pathlib import Path

from videoApp import app
from video_app_settings import get_settings

# Global variable to hold the profiler instance
profiler = cProfile.Profile()
server = None

def start_profiling():
    profiler.enable()


def stop_profiling_and_print_stats():
    profiler.disable()
    s = io.StringIO()
    sortby = pstats.SortKey.CUMULATIVE
    ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())


def signal_handler(signal, frame):
    settings = get_settings()
    
    # This function will be called when SIGINT is received
    print("SIGINT received, shutting down gracefully...")
    app.shutdown()  # This will cause the app to stop processing requests
    settings.stop_stream()  # This will cause the app to stop processing frames
    settings.delete_db()

    exit(0)


async def app_runner(host: str, port: int, profile: bool):
    config = Config(app=app, host=host, port=port, log_level="debug", workers=3)
    server = Server(config=config)

    if profile:
        start_profiling()

    signal.signal(signal.SIGINT, signal_handler)
    await server.serve()

    if profile:
        stop_profiling_and_print_stats()

if __name__ == "__main__":
    settings = get_settings()

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--host", default="0.0.0.0")
    argparser.add_argument("--port", default=14041)

    default_ml_model_config_path = Path(__file__).parent / "config" / "ml-model-config.yaml"

    argparser.add_argument(
        "--ml-model-config-file", default=str(default_ml_model_config_path), help="Path to the model config file"
    )

    default_node_config_path = Path(__file__).parent / "config" / "node-config.yaml"

    argparser.add_argument(
        "--node-config-file", default=str(default_node_config_path), help="Path to the node config file"
    )

    argparser.add_argument(
        "--source_weights_path",
        required=False,
        help="Path to the source weights file",
        type=str,
    )
    argparser.add_argument(
        "--source_all_videos_path",
        required=False,
        help="Path to the source video directory (optional if source_video_path is set)",
        type=str,
    )
    argparser.add_argument(
        "--source_video_path",
        required=False,
        help="Path to the source video file",
        type=str,
    )
    argparser.add_argument(
        "--confidence_threshold",
        default=0.3,
        help="Confidence threshold for the model",
        type=float,
    )
    argparser.add_argument(
        "--iou_threshold", default=0.7, help="Iou threshold for the model", type=float
    )
    parsedArgs = vars(argparser.parse_args())
    
    if parsedArgs["port"]:
        try:
            # Parse the port as an integer
            parsedArgs["port"] = int(parsedArgs["port"].strip())
        except ValueError:
            parsedArgs["port"] = 14041
        except AttributeError:
            # Already an integer
            pass

    if parsedArgs["ml_model_config_file"] and Path(parsedArgs["ml_model_config_file"]).exists():
        settings.set("ml_model_config_path", Path(parsedArgs["ml_model_config_file"]))
        opt = yaml.load(open(settings.get("ml_model_config_path")), Loader=yaml.FullLoader)
        opt.update(parsedArgs)
        settings.update_model_config(opt)

    if parsedArgs["node_config_file"] and Path(parsedArgs["node_config_file"]).exists():
        settings.set("node_config_path", Path(parsedArgs["node_config_file"]))
        
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    settings.set("log_level", LOG_LEVEL)

    if LOG_LEVEL == "DEBUG":
        log_level = logging.DEBUG
    elif LOG_LEVEL == "INFO":
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(level=log_level, filename="/tmp/app.log")

    try:
        asyncio.run(app_runner(parsedArgs["host"], parsedArgs["port"], profile=False))
    finally:
        app.shutdown()
