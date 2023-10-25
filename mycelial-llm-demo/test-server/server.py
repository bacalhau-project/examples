#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import json
import os


class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length"))
        body = json.loads(self.rfile.read(length))

        # Upper case and reverse the message provided
        body["message"] = body["message"].upper()[::1]

        with open(os.path.join("./outputs/", f"{body['key']}.json"), "w") as f:
            json.dump(body, f)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write('{"status": "ok"}'.encode(encoding="utf_8"))


def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
    server_address = ("127.0.0.1", 2112)
    print(f"Listening on {server_address}")
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


if __name__ == "__main__":
    run(server_class=ThreadingHTTPServer, handler_class=RequestHandler)
