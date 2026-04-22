---
name: ITF ledger HF-persistence
description: positions/bankrolls/cursor/ledger survive factory_reboot via end-of-tick HfApi upload + boot-time restore_ledgers.py
type: project
---

2026-04-22 (follow-up to compound-gap fix). Closed the attribution-reset gap IA flagged in `data/audit/itf-compound-gap-rca-2026-04-22.md`.

**Why:** HF Space /app is wiped on every factory_reboot. Without persistence, `positions.json`, `agent_bankrolls.json`, `fill_reconciliation_cursor.json`, `agent_ledger.jsonl` evaporate → 36h of per-agent attribution lost each restart.

**How to apply:** All 4 files now round-trip through the Space repo itself at `data/intraday/*`.
- `executor.persist_ledgers_to_hub()` uses `HfApi.create_commit` with up to 4 `CommitOperationAdd` ops per tick. Gated by module-global `_LEDGER_DIRTY` flag set by `_save_positions` / `_save_bankrolls` / `_save_recon_cursor` / `_append_ledger` so a no-mutation tick skips the Hub round-trip.
- `scripts/arena/hf-intraday-trading-floor/restore_ledgers.py` is new — runs in the Dockerfile CMD chain before uvicorn. Downloads the 4 files via `hf_hub_download`, swallows `EntryNotFoundError` / `RepositoryNotFoundError` (first-ever boot) and any other exception. Always exits 0 so a Hub outage can't block boot.
- Token resolution order: `HF_TOKEN_2` → `HF_TOKEN_NBA` → `HF_WRITE_TOKEN` → `NOMOS_HF_TOKEN` → `HF_TOKEN`. Space was missing all of them on first deploy — had to inject `HF_TOKEN_2` via `api.add_space_secret(...)` before persist fired.
- Max upload size for `agent_ledger.jsonl` is 5 MB (LFS-free repos cap at 10 MB). Larger files are skipped with a `skipped_big` note.

**Gotcha:** secrets on HF Spaces are invisible to `api.get_space_variables` (that only returns non-secret variables). Always inject via `add_space_secret` + restart; secrets take effect on regular restart, no factory_reboot needed.

Commit 5ef7383f0 (mon-ipad). HF SHA 3844ea83 (head after 4 snapshot commits). Files: `executor.py`, `app.py`, `restore_ledgers.py`, `Dockerfile` (adds restore step + `bash -c "python restore ... || true && exec python app.py"`), `requirements.txt` (adds `huggingface_hub>=0.24.0`).

Post-boot probe confirmed `unmatched_fills=0` + `skipped_seen=1` (cursor survived) and all 4 files present at `data/intraday/*` on the Hub after 3 ticks.
