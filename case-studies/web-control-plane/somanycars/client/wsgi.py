import argparse
import asyncio
import cProfile
import io
import os
import pstats
import signal

import yaml
from uvicorn import Config, Server

from app import app
from app_settings import Settings

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
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--port", type=int, default=8000)
    args = argparser.parse_args()
    argparser.add_argument("--profile", type=bool, default=False)

    settings = Settings()

    argparser.add_argument(
        "--config", default="config.yaml", help="Path to the config file"
    )

    if os.path.exists("config.yaml"):
        settings.model_config.merge_from_yaml("config.yaml")

    argparser.add_argument(
        "--source_weights_path",
        required=False,
        help="Path to the source weights file",
        type=str,
    )
    argparser.add_argument(
        "--source_video_path",
        required=False,
        help="Path to the source video file",
        type=str,
    )
    argparser.add_argument(
        "--target_video_path",
        required=False,
        help="Path to the target video file",
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
    args = argparser.parse_args()

    if not args.args:  # args priority is higher than yaml
        opt = vars(args)
        args = yaml.load(open(args.config), Loader=yaml.FullLoader)
        opt.update(args)
        args = opt
    else:  # yaml priority is higher than args
        opt = yaml.load(open(args.config), Loader=yaml.FullLoader)
        opt.update(vars(args))
        args = opt

    loop = asyncio.get_event_loop()
    # Register the signal handler for SIGINT
    signal.signal(signal.SIGINT, signal_handler)
    loop.run_until_complete(app_runner())

    app.shutdown()
