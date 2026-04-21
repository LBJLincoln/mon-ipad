#!/bin/bash
# Thin wrapper so cron doesn't need inline cd+; syntax (which was getting mangled).
cd /home/termius/mon-ipad || exit 1
/usr/bin/python3 scripts/ops/refresh_strategic_dashboard.py >> /tmp/strategic_dashboard.log 2>&1
