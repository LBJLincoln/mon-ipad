---
name: Browser-use + Hermes devcontainer + cross-repo integration (2026-04-20)
description: FRANKENSTEIN-2 shipped Codespaces post-create, VM installer, and dashboard/FEC cross-repo clients for the 3-Space browser+Hermes rollout owned by the other FRANKENSTEIN instance.
type: project
---

Parallel FRANKENSTEIN instance shipped 3 HF Spaces (LBJLincoln/nomos-browser-nba,
TESTforge42/nomos-browser-qa, LBJLincoln26/nomos-hermes-agent). This side wired
everything else:

- `.devcontainer/post-create.sh` + `devcontainer.json` (postCreateCommand,
  port 7860, NOUS_API_KEY/BROWSERUSE_API_KEY/*_URL secrets)
- `scripts/setup/install-browser-hermes.sh` — idempotent VM installer
- `scripts/agents/dashboard_qa_client.py` + `.github/workflows/dashboard-qa.yml`
- Mirror workflow in nomos-dashboard `.github/workflows/browser-qa.yml`
- `nomos-political-alpha/scripts/scrape_fec_edgar.py` stub (endpoint not yet)
- `scripts/agents/README.md` (client->Space map + cron recipes)
- CLAUDE.md "Codespaces + local install" subsection

**Why:** Research doc `data/research/hermes-browser-agents-2026-04-20.md`
prescribed Hermes + browser-use across NBA scraping / QA / orchestration.
The Spaces were only the HF side — codespaces/VM/sibling-repo integration
lives on the rest of the surface.

**How to apply:** When someone spins a fresh Codespace, post-create.sh runs
automatically. On the VM, `bash scripts/setup/install-browser-hermes.sh`
is safe to re-run. Any new client script MUST be added to
`scripts/agents/README.md` with a cron example.

**Traps noted:**
- `pip install` on this VM errors out without `--break-system-packages` (PEP 668).
- NousResearch upstream `scripts/install.sh` calls `npx playwright install
  --with-deps chromium` which needs passwordless sudo + ~5 min + can hang on
  apt-lock. Wrapped in `timeout 900` + treat all failures as non-fatal.
- The Mar 30 install left `~/.local/bin/hermes` as a broken symlink to
  `~/hermes-agent/cli.py` — actual repo is at `~/.hermes/hermes-agent/`.
  Fixed the symlink; detection now checks `-x` on `~/.local/bin/hermes`.
- browser-use 0.12.x doesn't expose `__version__` — use `pip show` instead.

**Verified end-to-end on VM:** uv 0.9.30, browser-use 0.12.6 (upgraded from
0.12.2), Hermes v0.10.0 (2026.4.16). Commit in mon-ipad `52b4bb169`
(FRANKENSTEIN-2 via safe_commit.sh), sibling commits `d8adc44` +
`2a18330`.
