#!/usr/bin/env python3
"""Local fictional forecast service. Responses are synthetic; no cache is modeled."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math

from config.params import PROFILES

VARIABLES = {variable for values in PROFILES.values() for variable in values}


def forecast(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    location = payload.get("location")
    if not isinstance(location, dict):
        raise ValueError("location must contain latitude and longitude")
    lat, lon = location.get("latitude"), location.get("longitude")
    for value, limit in ((lat, 90), (lon, 180)):
        if type(value) not in (int, float) or not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError("Invalid latitude or longitude")
    hours = payload.get("hours")
    if type(hours) is not int or not 1 <= hours <= 168:
        raise ValueError("hours must be an integer between 1 and 168")
    if payload.get("profile") not in PROFILES:
        raise ValueError("Unknown profile")
    variables = payload.get("variables")
    if (not isinstance(variables, list) or not variables or len(variables) > len(VARIABLES)
            or any(not isinstance(v, str) or v not in VARIABLES for v in variables)):
        raise ValueError("variables must be a nonempty list of supported names")
    series = []
    for hour in range(hours):
        wave = math.sin((hour + lat + lon) / 12)
        values = {"temperature": 15 + 5 * wave, "temperature_min": 10 + 5 * wave,
                  "temperature_max": 20 + 5 * wave, "precipitation": max(0, wave * 2),
                  "wind_speed": 10 + 3 * wave, "humidity": 60 + 10 * wave,
                  "pressure": 1010 + 5 * wave}
        series.append({"hour": hour, **{name: round(values[name], 2) for name in variables}})
    return {"synthetic": True, "location": location, "profile": payload["profile"], "forecast": series}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        encoded = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self.respond(200 if self.path == "/health" else 404,
                     {"status": "ok", "synthetic": True} if self.path == "/health" else {"error": "Not found"})

    def do_POST(self):
        if self.path != "/forecast":
            self.respond(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Request body must be between 1 and 65536 bytes")
            payload = json.loads(self.rfile.read(length))
            result = forecast(payload)
        except (ValueError, UnicodeError) as error:
            self.respond(400, {"error": str(error)})
            return
        self.respond(200, result)

    def log_message(self, format, *args):
        pass  # Avoid per-request console output during local load testing.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic forecast API listening at http://localhost:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
