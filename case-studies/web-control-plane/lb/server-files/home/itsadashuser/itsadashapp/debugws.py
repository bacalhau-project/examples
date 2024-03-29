from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
app.add_url_rule("/", "index", lambda: render_template("debugws.html"))

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")


@socketio.on("message")
def handle_message(data):
    print("received message: " + data)


if __name__ == "__main__":
    socketio.run(app, debug=True)
