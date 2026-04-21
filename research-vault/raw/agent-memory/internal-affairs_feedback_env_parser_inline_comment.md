---
name: env-local parser must strip inline comments
description: run_audit.py hf_token() parser silently swallowed trailing "# comment" into the token value, producing non-ASCII bytes that crashed httpx header encoding for all 3 fleets
type: feedback
---

Every agent that parses `.env.local` by hand (not via `dotenv`) MUST strip inline comments and trailing whitespace AFTER quote stripping. Bash treats `KEY="val"  # note` as `val`, but naive `line.split('=')[1].strip().strip('"')` keeps `val"  # note` after the closing quote, and that trailing payload often carries em-dashes or other UTF-8 chars that explode in httpx/urllib3 header encoding ("'ascii' codec can't encode '\u2014' position N").

**Why:** 2026-04-20T2342 audit run crashed with 3/3 fleets reporting the same `\u2014` error at position 68 of the Bearer header. Root cause traced to `HF_TOKEN_2="hf_..."        # LBJLincoln26 — rotated 2026-04-18` in `.env.local` — the comment with the em-dash was concatenated into the token. All 5 integrity checks were silently skipped on NBA + POL + PQTF. The crash surfaced as `result[key] = {"error": str(e)}` with `alerts=0`, meaning cron never paged.

**How to apply:**
- When writing env parsers: after quote stripping, cut the value at first unquoted whitespace or `#`. See fix in `scripts/audit/run_audit.py:44-56`.
- When reviewing audit output: `error` fields on a fleet are themselves an integrity red flag. Zero-alerts + three-fleet-errors = broken runner, not clean state. Consider promoting fleet-level `error` into the alert channel so the :40 cron pages on silent failures.
- When rotating HF tokens: prefer `KEY=value` on its own line, move the provenance comment to the line above.
