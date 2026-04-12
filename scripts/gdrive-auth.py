#!/usr/bin/env python3
"""
Headless Google Drive OAuth for rclone.
Generates an auth URL, user visits it, pastes the code, gets rclone token.
"""
import json
import urllib.request
import urllib.parse
import sys

# rclone's public desktop client ID (no secret needed for public clients)
# Using Google's gcloud client since we already have it
CLIENT_ID = "32555940559.apps.googleusercontent.com"
CLIENT_SECRET = "ZmssLNjJy2998hD4CTg2ejr2"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPES = "https://www.googleapis.com/auth/drive"

# Step 1: Generate auth URL
auth_url = (
    "https://accounts.google.com/o/oauth2/auth?"
    + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
)

print("\n" + "="*60)
print("GOOGLE DRIVE AUTH FOR RCLONE")
print("="*60)
print(f"\n1. Open this URL in your browser:\n\n{auth_url}\n")
print("2. Sign in with lahargnedebartoli@gmail.com")
print("3. Allow access to Google Drive")
print("4. Copy the authorization code and paste it below\n")

code = input("Authorization code: ").strip()

if not code:
    print("No code provided. Exiting.")
    sys.exit(1)

# Step 2: Exchange code for tokens
data = urllib.parse.urlencode({
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
try:
    resp = urllib.request.urlopen(req)
    token_data = json.loads(resp.read())
except Exception as e:
    print(f"Error exchanging code: {e}")
    sys.exit(1)

# Step 3: Build rclone token
from datetime import datetime, timedelta
expiry = (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).strftime("%Y-%m-%dT%H:%M:%SZ")

rclone_token = json.dumps({
    "access_token": token_data["access_token"],
    "token_type": "Bearer",
    "refresh_token": token_data.get("refresh_token", ""),
    "expiry": expiry,
})

# Step 4: Write rclone config
config_path = str(Path.home() / ".config" / "rclone" / "rclone.conf")
config = f"""[gdrive]
type = drive
client_id = {CLIENT_ID}
client_secret = {CLIENT_SECRET}
scope = drive
token = {rclone_token}
team_drive =
"""

with open(config_path, "w") as f:
    f.write(config)

print(f"\n✓ Token saved to {config_path}")
print("Testing connection...")

import subprocess
result = subprocess.run(["rclone", "about", "gdrive:"], capture_output=True, text=True)
if result.returncode == 0:
    print("✓ Google Drive connected!\n")
    print(result.stdout)
else:
    print(f"✗ Connection test failed: {result.stderr}")
