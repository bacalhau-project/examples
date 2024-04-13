import argparse

from flask_socketio import SocketIO

from app import flaskApp as app  # noqa: E402
from app import socketio  # noqa: E402

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--port", type=int, default=9595)
    args = arg_parser.parse_args()

    socketio = SocketIO(
        app,
        debug=True,
        use_reloader=True,
        port=args.port,
        cors_allowed_origins="*",
        async_mode="gevent",
    )
