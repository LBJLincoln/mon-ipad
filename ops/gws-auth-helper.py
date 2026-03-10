#!/usr/bin/env python3
"""
GWS Auth Helper — Headless VM OAuth for gws CLI
Solves the localhost redirect problem when using Termius/iPad.

Flow:
  1. Starts a proxy on a FIXED port (8085) on the VM
  2. Launches gws auth login in background
  3. Gives you a URL to open in your iPad browser
  4. When Google redirects to localhost, you paste the full redirect URL
  5. The helper forwards the auth code to gws's dynamic localhost port

Usage:
  python3 ops/gws-auth-helper.py

Or simpler manual flow:
  python3 ops/gws-auth-helper.py --manual
"""

import subprocess
import re
import sys
import time
import urllib.request
import urllib.error
import json
import socket
import os

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def manual_flow():
    """Manual OAuth code capture — works from any terminal."""
    print("\n=== GWS Manual Auth Flow ===\n")

    # Read client secret
    config_dir = os.path.expanduser("~/.config/gws")
    secret_file = os.path.join(config_dir, "client_secret.json")

    if not os.path.exists(secret_file):
        print(f"ERROR: {secret_file} not found")
        sys.exit(1)

    with open(secret_file) as f:
        secret = json.load(f)

    client_id = secret["installed"]["client_id"]
    client_secret = secret["installed"]["client_secret"]

    # Build OAuth URL with OOB redirect (manual copy-paste)
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/documents",
    ]
    scope_str = "%20".join(scopes)

    # Use urn:ietf:wg:oauth:2.0:oob for manual code entry
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    auth_url = (
        f"https://accounts.google.com/o/oauth2/auth"
        f"?scope={scope_str}"
        f"&access_type=offline"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&client_id={client_id}"
        f"&prompt=select_account+consent"
    )

    print("1. Open this URL in your browser (iPad/phone/laptop):\n")
    print(f"   {auth_url}\n")
    print("2. Sign in with your Google account")
    print("3. Click 'Allow' for all permissions")
    print("4. Google will show you an authorization code")
    print("5. Paste that code here:\n")

    code = input("Authorization code: ").strip()

    if not code:
        print("ERROR: No code provided")
        sys.exit(1)

    # Exchange code for tokens
    print("\nExchanging code for tokens...")

    token_data = (
        f"code={code}"
        f"&client_id={client_id}"
        f"&client_secret={client_secret}"
        f"&redirect_uri={redirect_uri}"
        f"&grant_type=authorization_code"
    ).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        tokens = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"ERROR: Token exchange failed: {e.code}")
        print(error_body)
        sys.exit(1)

    # Save as gws credentials file
    creds = {
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens.get("refresh_token", ""),
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    creds_file = os.path.join(config_dir, "credentials.json")
    with open(creds_file, "w") as f:
        json.dump(creds, f, indent=2)

    print(f"\nCredentials saved to {creds_file}")
    print(f"Access token: {tokens.get('access_token', '')[:20]}...")
    print(f"Refresh token: {'YES' if tokens.get('refresh_token') else 'NO'}")

    # Also set env var for immediate use
    print(f"\nTo use immediately:")
    print(f"  export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE={creds_file}")
    print(f"  gws drive files list --params '{{\"pageSize\": 3}}'")

    # Test it
    print("\nTesting...")
    os.environ["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = creds_file
    result = subprocess.run(
        ["gws", "drive", "files", "list", "--params", '{"pageSize": 2}'],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0 and "error" not in result.stdout.lower():
        print(f"SUCCESS! Drive access working.")
        print(result.stdout[:200])
    else:
        print(f"Test result: {result.stdout[:200]}")
        if result.stderr:
            print(f"Stderr: {result.stderr[:200]}")


def proxy_flow():
    """Proxy flow — intercepts gws auth login redirect."""
    print("\n=== GWS Auth Proxy Flow ===\n")
    print("Starting gws auth login and intercepting the OAuth URL...\n")

    # Start gws auth login and capture the URL
    proc = subprocess.Popen(
        ["gws", "auth", "login"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Read output to find the URL
    auth_url = None
    port = None
    for line in proc.stdout:
        line = line.strip()
        print(f"  gws: {line}")
        if "accounts.google.com" in line:
            auth_url = line
            # Extract the redirect port
            m = re.search(r'localhost:(\d+)', line)
            if m:
                port = int(m.group(1))
            break

    if not auth_url or not port:
        print("ERROR: Could not find auth URL from gws")
        proc.kill()
        sys.exit(1)

    print(f"\nGWS is waiting on localhost:{port}")
    print(f"\n1. Open the URL above in your browser")
    print(f"2. After Google auth, your browser will try to redirect to localhost:{port}")
    print(f"3. It will FAIL (expected). Copy the FULL URL from your browser's address bar")
    print(f"4. Paste it here:\n")

    redirect_url = input("Paste the redirect URL: ").strip()

    if not redirect_url:
        print("ERROR: No URL provided")
        proc.kill()
        sys.exit(1)

    # Extract the query string and forward to gws's localhost
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redirect_url)
    query = parsed.query

    # Forward to gws
    forward_url = f"http://localhost:{port}/?{query}"
    print(f"\nForwarding to gws at {forward_url}...")

    try:
        req = urllib.request.Request(forward_url)
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"Response: {resp.status}")
        print(resp.read().decode()[:200])
    except Exception as e:
        print(f"Forward result: {e}")

    # Wait for gws to finish
    proc.wait(timeout=10)
    print("\nDone! Try: gws drive files list --params '{\"pageSize\": 3}'")


if __name__ == "__main__":
    if "--manual" in sys.argv:
        manual_flow()
    elif "--proxy" in sys.argv:
        proxy_flow()
    else:
        print("GWS Auth Helper for Headless VM")
        print("")
        print("Options:")
        print("  --manual   Manual code copy-paste (recommended)")
        print("  --proxy    Intercept gws redirect URL")
        print("")
        print("Recommended: python3 ops/gws-auth-helper.py --manual")
        manual_flow()
