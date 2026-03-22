#!/usr/bin/env python3
"""
One-time WHOOP OAuth2 authorization script.

Run this whenever your tokens expire or become invalid:
  python3 get_tokens.py

It will:
  1. Open your browser to the WHOOP authorization page
  2. Start a local server to catch the callback
  3. Exchange the auth code for tokens
  4. Write WHOOP_ACCESS_TOKEN and WHOOP_REFRESH_TOKEN into ../.env

Prerequisites: WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must already be in .env,
and http://localhost:8080 must be registered as a redirect URI in your WHOOP app.
"""

import os
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

REDIRECT_URI = "http://localhost:8080"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPES = "read:recovery read:sleep read:workout read:cycles offline"

_auth_code: str | None = None
_server: HTTPServer | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            _auth_code = qs["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Error: no code in callback.</h2>")
        threading.Thread(target=_server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass  # silence request logs


def _start_server():
    global _server
    _server = HTTPServer(("localhost", 8080), _CallbackHandler)
    _server.serve_forever()


def main():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)
    load_dotenv(env_path)

    client_id = os.environ.get("WHOOP_CLIENT_ID")
    client_secret = os.environ.get("WHOOP_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set in .env")

    # Start callback server in background
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()

    # Open browser
    params = urlencode({"client_id": client_id, "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": SCOPES})
    url = f"{AUTH_URL}?{params}"
    print(f"Opening browser for WHOOP authorization...\n{url}\n")
    webbrowser.open(url)

    print("Waiting for authorization (approve in your browser)...")
    t.join()

    if not _auth_code:
        raise SystemExit("No authorization code received.")

    # Exchange code for tokens
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]
    refresh_token = payload["refresh_token"]

    # Write back to .env
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.read()
        # Update existing keys if present, otherwise append
        for key, val in [("WHOOP_ACCESS_TOKEN", access_token), ("WHOOP_REFRESH_TOKEN", refresh_token)]:
            if re.search(rf"(?m)^{key}=", content):
                content = re.sub(rf"(?m)^{key}=.*$", f"{key}={val}", content)
            else:
                content += f"\n{key}={val}"
        with open(env_path, "w") as f:
            f.write(content)
        print(f"Tokens written to {env_path}")
    else:
        print(f"WHOOP_ACCESS_TOKEN={access_token}")
        print(f"WHOOP_REFRESH_TOKEN={refresh_token}")
        print("(No .env file found — copy the above into your .env manually.)")


if __name__ == "__main__":
    main()
