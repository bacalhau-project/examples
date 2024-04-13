import argparse
import asyncio
import cProfile
import io
import os
import pstats
import signal

import yaml
from uvicorn import Config, Server

from pathlib import Path

from app import app
from app_settings import get_settings

# Global variable to hold the profiler instance
profiler = cProfile.Profile()


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
    loop = asyncio.get_event_loop()
    # This function will be called when SIGINT is received
    print("SIGINT received, shutting down gracefully...")
    loop.stop()  # Stops the event loop, causing the server to shut down


async def app_runner(port: int, profile: bool):
    config = Config(app=app, host="0.0.0.0", port=port, lifespan="on")
    server = Server(config=config)

    if profile:
        start_profiling()

    await server.serve()

    if profile:
        stop_profiling_and_print_stats()

if __name__ == "__main__":
    settings = get_settings()

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--port", type=int, default=14041)

    default_config_path = Path(__file__).parent / "config" / "model-config.yaml"

    argparser.add_argument(
        "--ml-model-config-file", default=str(default_config_path), help="Path to the model config file"
    )

    default_config_path = Path(__file__).parent / "config" / "node-config.yaml"

    argparser.add_argument(
        "--node-config-file", default=str(default_config_path), help="Path to the node config file"
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

    argparser.add_argument(
        "--skip_frames", default=1, help="Only process every n-th frame", type=int
    )
    parsedArgs = vars(argparser.parse_args())

    if parsedArgs["ml_model_config_file"] and Path(parsedArgs["ml_model_config_file"]).exists():
        settings.set("ml_model_config_path", Path(parsedArgs["ml_model_config_file"]))
        opt = yaml.load(open(settings.get("ml_model_config_path")), Loader=yaml.FullLoader)
        opt.update(parsedArgs)
        parsedArgs = opt

    if parsedArgs["node_config_file"] and Path(parsedArgs["node_config_file"]).exists():
        settings.set("node_config_path", Path(parsedArgs["node_config_file"]))

    if parsedArgs:
        settings.update_model_config(parsedArgs)

    try:
        # Register the signal handler
        # for SIGINT
        signal.signal(signal.SIGINT, signal_handler)
        asyncio.run(app_runner(parsedArgs["port"], profile=False))
    finally:
        app.shutdown()
