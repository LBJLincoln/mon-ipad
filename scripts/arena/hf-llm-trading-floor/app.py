import json
import sys
_payload = json.load(open('/tmp/_push_payload.json'))
print(_payload['nba'][:100])