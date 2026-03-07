Sync directives from mon-ipad to all satellite repos.

Steps:
1. Run `bash scripts/push-directives.sh`
2. Verify each satellite repo received the update (check git log of each)
3. Report which repos were updated successfully and which failed
4. If any failed, show the error and suggest a fix
