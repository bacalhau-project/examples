from app import flaskApp as app  # noqa: E402
from app import socketio  # noqa: E402

if __name__ == "__main__":
    socketio.run(
        app,
        debug=True,
        cors_allowed_origins="*",
        async_mode="gevent",
    )
