import logging

from ultralytics import YOLO
from vidgear.gears.asyncio import WebGear
from vidgear.gears.asyncio.helper import reducer

import argparse
import asyncio
import cProfile
import io
import os
import pstats
import signal

import yaml
from uvicorn import Config, Server
from starlette.routing import Mount, Route
import logging

from pathlib import Path

testapp = WebGear(logging=True)

async def main():
    return "Hello, World!"

async def app_runner():
    config = Config(app=testapp, host="0.0.0.0")
    server = Server(config=config)

    await server.serve()

testapp.routes.append(Route("/", endpoint=main))

if __name__ == "__main__":
        
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    if LOG_LEVEL == "DEBUG":
        log_level = logging.DEBUG
    elif LOG_LEVEL == "INFO":
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(level=log_level)

    asyncio.run(app_runner())
