#!/bin/bash
# Update dashboard data — run via cron or monitor agent
cd /home/termius/mon-ipad
python3 -c "
import json, os
try:
    health = json.load(open('data/health-status.json'))
except: health = {}
agents = {}
for name in ['monitor', 'eval', 'ingest', 'pipeline', 'docs']:
    pid_file = f'data/agents/{name}.pid'
    status = 'STOPPED'
    if os.path.exists(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            os.kill(pid, 0)
            status = 'RUNNING'
        except: pass
    agents[name] = {'status': status}
health['agents'] = agents
with open('docs/health-status.json', 'w') as f:
    json.dump(health, f, indent=2)
"
