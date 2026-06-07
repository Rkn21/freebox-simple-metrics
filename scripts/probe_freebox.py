"""Probe a Freebox token without Home Assistant.

Usage:
  set FREEBOX_APP_TOKEN=...
  set FREEBOX_APP_ID=fr.rkn21.freebox_simple_metrics
  python scripts/probe_freebox.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request


HOST = os.environ.get("FREEBOX_HOST", "192.168.0.254")
APP_ID = os.environ.get("FREEBOX_APP_ID", "fr.rkn21.freebox_simple_metrics")
APP_TOKEN = os.environ.get("FREEBOX_APP_TOKEN")


def request(method: str, path: str, *, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Fbx-App-Auth"] = token
    req = urllib.request.Request(
        f"http://{HOST}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode())
    if payload.get("success") is False:
        raise RuntimeError(payload)
    return payload.get("result", payload)


def main() -> int:
    if not APP_TOKEN:
        print("FREEBOX_APP_TOKEN is required", file=sys.stderr)
        return 2

    discovery = request("GET", "/api_version")
    major = str(discovery["api_version"]).split(".", maxsplit=1)[0]
    login = request("GET", f"/api/v{major}/login/")
    password = hmac.new(
        APP_TOKEN.encode(),
        login["challenge"].encode(),
        hashlib.sha1,
    ).hexdigest()
    session = request(
        "POST",
        f"/api/v{major}/login/session/",
        body={"app_id": APP_ID, "password": password},
    )
    session_token = session["session_token"]
    connection = request("GET", f"/api/v{major}/connection/", token=session_token)
    switch_status = request("GET", f"/api/v{major}/switch/status/", token=session_token)
    print(
        json.dumps(
            {
                "box": discovery.get("box_model_name"),
                "api_version": discovery.get("api_version"),
                "connection_state": connection.get("state"),
                "media": connection.get("media"),
                "switch_ports": len(switch_status),
                "connected_ports": sum(1 for port in switch_status if port.get("link") == "up"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as err:
        print(err.read().decode(), file=sys.stderr)
        raise
