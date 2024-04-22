import asyncio
import cProfile
import io
import pstats
import signal

from app import app  # Import the FastAPI app object

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


async def app_runner():
    # Import uvicorn's Config and Server classes for more control over the server instance
    from uvicorn import Config, Server

    config = Config(app=app, host="0.0.0.0", port=14041)
    server = Server(config=config)

    start_profiling()

    await server.serve()
    stop_profiling_and_print_stats()


def signal_handler(signal, frame):
    loop = asyncio.get_event_loop()
    # This function will be called when SIGINT is received
    print("SIGINT received, shutting down gracefully...")
    loop.stop()  # Stops the event loop, causing the server to shut down


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # Register the signal handler for SIGINT
    signal.signal(signal.SIGINT, signal_handler)
    loop.run_until_complete(app_runner())
