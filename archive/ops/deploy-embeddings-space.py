#!/usr/bin/env python3
"""
Deploy nomos-embeddings-api files from lbjlincoln/nomos-embeddings-api
to Nomos42/nomos-embeddings-2 on HuggingFace.

Uses:
  - urllib (IPv4-fixed, custom SSL) to list + download source files
  - huggingface_hub to upload (handles multipart commit API correctly)
"""

import os
import sys
import ssl
import json
import socket
import urllib.request
import urllib.error
import tempfile
from pathlib import Path

# ── IPv4 fix ─────────────────────────────────────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

# ── SSL context ──────────────────────────────────────────────────────────────
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Config ───────────────────────────────────────────────────────────────────
SRC_TOKEN = os.environ.get("HF_TOKEN", "")
DST_TOKEN = os.environ.get("HF_TOKEN_3", "")

SRC_SPACE = "lbjlincoln/nomos-embeddings-api"
DST_SPACE = "Nomos42/nomos-embeddings-2"

SRC_TREE  = f"https://huggingface.co/api/spaces/{SRC_SPACE}/tree/main"
SRC_RAW   = f"https://huggingface.co/spaces/{SRC_SPACE}/raw/main"

# ── Helpers ──────────────────────────────────────────────────────────────────
def hf_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=60) as r:
        return r.read()

def list_source_files():
    print(f"Listing files in {SRC_SPACE} ...")
    raw = hf_get(SRC_TREE, SRC_TOKEN)
    tree = json.loads(raw)
    files = [e["path"] for e in tree if e.get("type") == "file"]
    print(f"  Found {len(files)} file(s): {files}")
    return files

def download_file(path):
    url = f"{SRC_RAW}/{path}"
    print(f"  Downloading: {path}")
    data = hf_get(url, SRC_TOKEN)
    print(f"    {len(data)} bytes")
    return data

def check_space_status(api):
    try:
        info = api.space_info(DST_SPACE)
        stage = getattr(getattr(info, "runtime", None), "stage", "UNKNOWN")
        sdk   = getattr(info, "sdk", "?")
        return str(stage), str(sdk)
    except Exception as e:
        return f"ERROR: {e}", "?"

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not SRC_TOKEN:
        print("ERROR: HF_TOKEN not set")
        sys.exit(1)
    if not DST_TOKEN:
        print("ERROR: HF_TOKEN_3 not set")
        sys.exit(1)

    # Import huggingface_hub (handles multipart commit API)
    try:
        from huggingface_hub import HfApi, CommitOperationAdd
    except ImportError:
        print("ERROR: huggingface_hub not installed — run: pip install huggingface_hub")
        sys.exit(1)

    api = HfApi(token=DST_TOKEN)

    print("=" * 60)
    print(f"Source : {SRC_SPACE}")
    print(f"Dest   : {DST_SPACE}")
    print("=" * 60)

    # 1. List source files
    try:
        files = list_source_files()
    except Exception as e:
        print(f"FATAL listing source files: {e}")
        sys.exit(1)

    if not files:
        print("No files found in source space. Aborting.")
        sys.exit(1)

    # 2. Download all files into memory
    file_contents = {}
    for path in files:
        try:
            file_contents[path] = download_file(path)
        except Exception as e:
            print(f"  ERROR downloading {path}: {e}")

    if not file_contents:
        print("FATAL: failed to download any files.")
        sys.exit(1)

    # 3. Build commit operations + upload via huggingface_hub
    print(f"\nUploading {len(file_contents)} file(s) to {DST_SPACE} ...")
    operations = []
    for path, data in file_contents.items():
        operations.append(
            CommitOperationAdd(
                path_in_repo=path,
                path_or_fileobj=data,   # bytes accepted
            )
        )

    uploaded = []
    failed   = list(set(files) - set(file_contents.keys()))  # download failures

    try:
        commit = api.create_commit(
            repo_id=DST_SPACE,
            repo_type="space",
            operations=operations,
            commit_message="Deploy: copy from lbjlincoln/nomos-embeddings-api",
        )
        uploaded = list(file_contents.keys())
        print(f"  Commit URL: {commit}")
    except Exception as e:
        print(f"  ERROR during commit: {e}")
        failed.extend(list(file_contents.keys()))

    # 4. Check space status
    print("\nChecking destination space status ...")
    stage, sdk = check_space_status(api)

    # 5. Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"Uploaded ({len(uploaded)}): {uploaded}")
    if failed:
        print(f"Failed   ({len(failed)}): {failed}")
    print(f"Space stage : {stage}")
    print(f"Space SDK   : {sdk}")
    print(f"Space URL   : https://huggingface.co/spaces/{DST_SPACE}")
    print("=" * 60)

    sys.exit(0 if not failed else 1)

if __name__ == "__main__":
    main()
