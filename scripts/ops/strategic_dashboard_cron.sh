#!/bin/bash
# Thin wrapper so cron doesn't need inline cd+; syntax (which was getting mangled).
cd /home/termius/mon-ipad || exit 1
# Load Alpaca paper creds so ITF live P&L lands in the dashboard
[ -f .env.local ] && . .env.local
/usr/bin/python3 scripts/ops/refresh_strategic_dashboard.py >> /tmp/strategic_dashboard.log 2>&1
