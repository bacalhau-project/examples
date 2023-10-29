from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import json
import os

from .query import get_query
from .tokens import get_replacements


database = None


def make_request_handler(data, outputs, limit):
    def maker(a, b, c):
        return RequestHandler(data, outputs, limit, a, b, c)

    return maker


def load_data(path):
    print("Loading data from disk")
    return json.load(open(path, "r"))


class RequestHandler(BaseHTTPRequestHandler):
    data = None

    def __init__(self, data_path, outputs, limit, a, b, c):
        global database
        self.data_path = data_path
        self.limit = limit
        self.output_path = os.path.abspath(outputs)

        if database is None:
            print(f"Loading data from {self.data_path}")
            database = load_data(self.data_path)
            print(f"Loaded {len(database)} entries")

        super(RequestHandler, self).__init__(a, b, c)

    def send_ok_response(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write('{"status": "ok"}'.encode(encoding="utf_8"))

    def do_POST(self):
        global database

        if self.path == "/reload":
            print(f"Re-loading data from {self.data_path}")
            database = load_data(self.data_path)
            print(f"Loaded {len(database)} entries")
            self.send_ok_response()
            return

        length = int(self.headers.get("content-length"))
        body = json.loads(self.rfile.read(length))

        print("Received ", body)

        q = get_query(body["message"], database, self.limit)
        if q:
            replacements = get_replacements(body["message"])
        else:
            replacements = []

        result = {
            "query": q or "",
            "replacements": replacements or [],
        }

        # Dump the result json into a string for the response...
        body["message"] = json.dumps(result)

        try:
            output_file = os.path.join(self.output_path, f"{body['key']}.json")
            with open(output_file, "w") as f:
                json.dump(body, f)

            print(f"Wrote response to: {output_file}")
        except:
            print("Failed to write to output")
            self.send_response(500)
            return

        self.send_ok_response()


def run(data_path, outputs, limit):
    server_address = ("0.0.0.0", 2112)
    print(f"Listening on {server_address}")
    httpd = HTTPServer(server_address, make_request_handler(data_path, outputs, limit))
    httpd.serve_forever()
