#!/usr/bin/env python3
import urllib.request, json, sys
try:
    resp = urllib.request.urlopen("http://localhost:5678/healthz", timeout=5)
    print(json.dumps({"status": "healthy", "code": resp.getcode()}))
except Exception as e:
    print(json.dumps({"status": "unhealthy", "error": str(e)}))
    sys.exit(1)
