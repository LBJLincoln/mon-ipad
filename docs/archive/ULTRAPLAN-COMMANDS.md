# ULTRAPLAN / Cloud Execution — Copy-Paste Commands

> Heavy or long-running work that should NOT run on this 1-vCPU/969MB VM.
> Pick a surface, copy the command/prompt, paste in the right place.

---

## 1. Claude Code Cloud (code.claude.com — Pro/Max/Team plans)

Best for: long autonomous research, multi-agent swarms, parallel /ultraplan.
URL: https://code.claude.com → New Cloud Session → paste the prompt.

### Prompt template — "deep research"
```
You are running in Claude Code Cloud. Repo: github.com/LBJLincoln/mon-ipad.
Mission: <ONE concrete goal>. Budget: 60 min. End state: PR opened with
description + test plan. Use /ultraplan to break down before coding.

Constraints:
- ZERO ML on local — all heavy compute on HF Spaces
- Engine parity: features/engine.py == hf-space/features/engine.py
- 1 fix per iteration, commit each
- ALWAYS git push after committing
```

### Prompt template — "ship a feature"
```
Repo: LBJLincoln/nomos-dashboard. Ship: <feature>. End state: deployed to
Vercel, screenshot in PR, no console errors. Use TaskCreate to plan steps.
```

---

## 2. GitHub Actions — ad-hoc dispatch

Best for: scheduled / repeatable heavy jobs. Already wired:

```bash
# Trigger Trading Floor monitor refresh
gh workflow run trading-floor.yml -R LBJLincoln/mon-ipad

# Trigger backtest swarm (CPCV gate)
gh workflow run backtest-swarm.yml -R LBJLincoln/mon-ipad

# Trigger ZeroGPU H200 burst (15 min free / day)
gh workflow run gpu-burst.yml -R LBJLincoln/mon-ipad

# View last run status
gh run list -R LBJLincoln/mon-ipad --workflow trading-floor.yml -L 3
```

### Create a one-shot ultraplan workflow
```bash
gh workflow run ultraplan-oneshot.yml -R LBJLincoln/mon-ipad \
  -f task="Audit all 9 council JSONs and propose merges" \
  -f budget_min=30
```
(Workflow file: `.github/workflows/ultraplan-oneshot.yml` — needs to exist.)

---

## 3. GitHub Codespaces — full Linux VM with Claude installed

Best for: when you need a real machine (16GB RAM, 4 CPU) for an hour or two.

```bash
# Create + attach
gh codespace create -R LBJLincoln/mon-ipad --machine standardLinux32gb -b main
gh codespace ssh -c <name>

# Inside the codespace:
cd /workspaces/mon-ipad
claude --print --dangerously-skip-permissions "<your prompt>"

# Tear down when done
gh codespace stop -c <name>
gh codespace delete -c <name>
```

---

## 4. HF Space — long-running ML / LLM job

Best for: training, evaluation, anything that needs >24h or stable IP.

```bash
# Restart any space (force fresh build)
curl -X POST -H "Authorization: Bearer $HF_TOKEN_LLM" \
  https://huggingface.co/api/spaces/Nomos42/nomos-cpu-gemma4/restart

# Trigger a run via FastAPI
curl -X POST https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/run \
  -H "Content-Type: application/json" \
  -d '{"design": "day-bucket-v3"}'

# Status
curl https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status | jq

# Mutate any agent's risk
curl -X POST https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/mutate \
  -H "Content-Type: application/json" \
  -d '{"agent": "qwen-quant", "risk_tolerance": 0.45}'
```

---

## 5. Modal — serverless GPU bursts

Best for: 15min-2hr GPU jobs (training, embeddings, LLM eval).

```bash
# Run any script with A10G GPU
modal run scripts/gpu-burst/modal-burst.py

# Run a custom one-shot
modal run --gpu A10G --timeout 3600 -- python -c "
import torch
print(torch.cuda.get_device_name(0))
"
```

---

## 6. Paperspace Gradient — free GPU notebook (unlimited restarts)

URL: https://console.paperspace.com → Notebooks → New → Free GPU.
Then paste in the first cell:
```python
!git clone https://github.com/LBJLincoln/mon-ipad.git
%cd mon-ipad
!pip install -r requirements.txt
!python scripts/karpathy/nba_loop.py --gpu --gens 200
```

---

## 7. Lightning.ai (creds in `.env.local` as LIGHTNING_*)

```bash
ssh -i ~/.ssh/lightning_key user@<lightning-vm-ip>
# Inside: full 22h GPU session, T4 free tier
```

---

## Quick reference — when to use what

| Task                                  | Surface                |
|---------------------------------------|------------------------|
| 60-min autonomous research            | Claude Code Cloud      |
| Ship a dashboard feature              | Claude Code Cloud      |
| Heavy ML training (>1hr)              | Modal / Paperspace     |
| Stable LLM endpoint                   | HF Space               |
| Multi-file refactor needing real CPU  | Codespace              |
| Scheduled job (cron-like)             | GitHub Actions         |
| GPU evolution loop                    | Kaggle / Paperspace    |
