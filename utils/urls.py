"""Serialize the fictional API contract as Siege POST request lines."""
import json


def generate_urls(requests, base_url):
    return [
        f"{base_url.rstrip('/')}/forecast POST {json.dumps(payload, separators=(',', ':'))}"
        for payload in requests
    ]
