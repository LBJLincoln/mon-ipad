# Kaggle GPU Automation Setup Guide

> Direct GPU kernel management from mon-ipad VM via Kaggle CLI

## 1-Minute Setup

```bash
# 1. Install CLI
pip install kaggle

# 2. Download API credentials
#    Visit: https://www.kaggle.com/settings/account
#    Click: "Create New Token"
#    Copy downloaded kaggle.json to:
mkdir -p ~/.kaggle
cp ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

# 3. Test
kaggle kernels list -m

# 4. Run GPU evolution
bash scripts/kaggle-gpu-evolution.sh
```

## Step-by-Step Setup

### Step 1: Get Kaggle API Credentials

1. Go to https://www.kaggle.com/settings/account
2. Scroll down to **"API"** section
3. Click **"Create New Token"** button
4. This downloads `kaggle.json` to your Downloads folder

Your `kaggle.json` looks like:

```json
{
  "username": "myusername",
  "key": "abc123def456..."
}
```

### Step 2: Place Credentials

```bash
mkdir -p ~/.kaggle
cp ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json
```

**IMPORTANT:** File permissions must be `600` (user read/write only).

```bash
ls -la ~/.kaggle/kaggle.json
# Should show: -rw------- 1 user group 100 Mar 26 14:30 /home/user/.kaggle/kaggle.json
```

### Step 3: Verify Installation

```bash
# Install Kaggle CLI
pip install kaggle

# Test authentication
kaggle competitions list --page-size 1

# Should output something like:
# ref                       deadline    category              reward  teamCount  userCount
# ---                       --------    --------              ------  ---------  ---------
# ...
```

### Step 4: Test Kernel Operations

```bash
# List your existing kernels
kaggle kernels list -m

# Check status of a kernel (if you have one)
kaggle kernels status myusername/some-kernel
```

## Automated GPU Evolution

### Quick Run (Manual)

```bash
bash scripts/kaggle-gpu-evolution.sh
```

**Output:**
- Uploads `nomos-nba-agent/colab/nba_gpu_v2.ipynb` to Kaggle
- Auto-starts GPU kernel execution (T4 by default)
- Polls status every 30-120 seconds
- Downloads results to `./data/kaggle_results/`
- Parses metrics and commits to git

### Using the Python Manager Directly

```bash
python3 scripts/kaggle_kernel_manager.py \
  --username myusername \
  --kernel-slug nba-quant-gpu-v2 \
  --notebook ./nomos-nba-agent/colab/nba_gpu_v2.ipynb \
  --wait \
  --timeout-minutes 180 \
  --output-dir ./data/kaggle_results
```

**Arguments:**

| Arg | Default | Description |
|-----|---------|-------------|
| `--username` | (required) | Your Kaggle username |
| `--kernel-slug` | (required) | Kernel name (e.g., `nba-quant-gpu-v2`) |
| `--notebook` | (optional) | Path to .ipynb to push |
| `--wait` | false | Wait for completion |
| `--timeout-minutes` | 180 | Max wait time |
| `--kernel-timeout-seconds` | 7200 | Kernel execution timeout |
| `--output-dir` | `./kaggle_outputs` | Where to save results |
| `--no-download` | false | Skip downloading outputs |
| `--status-only` | false | Just check status (no push) |

### Just Check Status

```bash
python3 scripts/kaggle_kernel_manager.py \
  --username myusername \
  --kernel-slug nba-quant-gpu-v2 \
  --status-only

# Output: Status: complete
```

## Cron Integration

Add to `autonomous-cycle.sh` (runs every 4 hours):

```bash
# === Kaggle GPU Evolution ===
if command -v kaggle &>/dev/null && [ -f ~/.kaggle/kaggle.json ]; then
    log "Running Kaggle GPU evolution..."
    bash scripts/kaggle-gpu-evolution.sh >> data/agent-activity.json 2>&1 || log "Kaggle GPU evolution failed (continuing)"
fi
```

Or create standalone cron job:

```bash
# Every 12 hours at 2am and 2pm
0 2,14 * * * cd /home/lahargnedebartoli/mon-ipad && bash scripts/kaggle-gpu-evolution.sh >> data/agent-kaggle.log 2>&1
```

## Available GPU Accelerators

On Kaggle free tier, you get:

- **T4 GPU** (default, most common) — 15GB VRAM
- **P100 GPU** (higher tier, rare) — 16GB VRAM

Specify explicitly in the Python manager:

```python
mgr.push_kernel(
    Path("nba_gpu_v2.ipynb"),
    accelerator="NvidiaTeslaT4"  # or "NvidiaA100"
)
```

Or via CLI metadata in `kernel-metadata.json`:

```json
{
  "enable_gpu": true,
  "accelerator": "NvidiaTeslaT4"
}
```

## Monitoring Progress

### Real-Time via CLI

```bash
# Check status every 60 seconds in a loop
while true; do
  kaggle kernels status myusername/nba-quant-gpu-v2
  sleep 60
done
```

### Via Python Manager

```python
from scripts.kaggle_kernel_manager import KaggleKernelManager

mgr = KaggleKernelManager("myusername", "nba-quant-gpu-v2")

# Get current status
status = mgr.get_status()
print(f"Status: {status}")  # queued, running, complete, failed, unknown

# Wait up to 3 hours
if mgr.wait_for_completion(max_wait_minutes=180):
    print("✓ Done!")
    mgr.download_outputs("./results")
else:
    print("✗ Timeout or failed")
```

## Downloading Results

### Via CLI

```bash
# Download all outputs
kaggle kernels output myusername/nba-quant-gpu-v2 -p ./results

# Download only .json files
kaggle kernels output myusername/nba-quant-gpu-v2 -p ./results --file-pattern ".*\.json$"

# Overwrite existing files
kaggle kernels output myusername/nba-quant-gpu-v2 -p ./results -o
```

### Via Python Manager

```python
mgr.download_outputs("./kaggle_results", force_overwrite=True)
```

## Troubleshooting

### "Kernel not found"

**Problem:** `Error: Kernel not found`

**Solution:** Check kernel slug format:
```bash
kaggle kernels list -m
# Copy exact slug from output, e.g., "myusername/nba-quant-gpu-v2"
```

### "Credentials not found"

**Problem:** `HTTP 401 Unauthorized`

**Solution:**
```bash
# Verify file exists
cat ~/.kaggle/kaggle.json

# Check permissions
ls -la ~/.kaggle/kaggle.json
# Should be: -rw------- (600)

# Regenerate if needed
# 1. Go to https://www.kaggle.com/settings/account
# 2. Remove old API key
# 3. Create new token
# 4. Save to ~/.kaggle/kaggle.json
```

### "Notebook not found"

**Problem:** `Error: Notebook not found` during push

**Solution:** Check the notebook file name in `kernel-metadata.json`:
```json
{
  "code_file": "nba_gpu_v2.ipynb"  // Must match actual filename
}
```

Also verify file exists:
```bash
ls -la ./nba_gpu_v2.ipynb
```

### "GPU not allocated"

**Problem:** Kernel runs on CPU instead of GPU

**Solution:** Ensure metadata has `enable_gpu: true`:
```json
{
  "enable_gpu": true,
  "accelerator": "NvidiaTeslaT4"
}
```

Also check GPU quota at https://www.kaggle.com/settings/usage

### No output files downloaded

**Problem:** `kaggle kernels output` returns empty

**Solution:** Kernel may still be running or failed:
```bash
# Check status
kaggle kernels status myusername/nba-quant-gpu-v2

# View recent kernel logs (limited availability)
kaggle kernels output myusername/nba-quant-gpu-v2 -p ./logs
```

## Advanced: Kernel Metadata Reference

Full `kernel-metadata.json` example:

```json
{
  "id": "myusername/nba-quant-gpu-v2",
  "title": "NBA Quant GPU Evolution v2",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": false,
  "enable_gpu": true,
  "enable_internet": true,
  "code_file": "nba_gpu_v2.ipynb",
  "dataset_sources": [
    "myusername/nba-dataset"
  ],
  "competition_sources": [],
  "kernel_sources": []
}
```

**Fields:**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | str | (required) | Format: "username/slug" |
| `title` | str | (required) | Human-readable name |
| `language` | str | (required) | python / r / rmarkdown |
| `kernel_type` | str | (required) | script / notebook |
| `is_private` | bool | true | Public or private kernel |
| `enable_gpu` | bool | false | T4 GPU (free tier) |
| `enable_internet` | bool | false | HTTP access (needed for pip install) |
| `code_file` | str | (required) | Path to .ipynb/.py |
| `dataset_sources` | list | [] | Linked datasets |
| `competition_sources` | list | [] | Linked competitions |
| `kernel_sources` | list | [] | Linked kernels |

## Alternatives if Kaggle Account Broken

If your Kaggle account is down (401/403 errors):

**Option 1: Google Colab** (verified working)
- Free T4 GPU, 4-12 hour sessions
- Use existing `nomos-nba-agent/colab/nba_gpu_v2.ipynb`
- See `CLAUDE.md` for Drive persistence setup

**Option 2: Modal.com** (recommended)
- $30/mo free (Starter tier)
- Per-second billing, serverless
- Up to A100 GPU
- No session limits
- Can run evolution continuously

**Option 3: Lightning.ai** (planned)
- 22 GPU-hr/mo free (credits arrive Apr 1 2026)
- Persistent storage, no disconnects
- Account: `moretalexis24`

## References

- **Official Kaggle CLI:** https://github.com/Kaggle/kaggle-cli
- **Kaggle API Docs:** https://www.kaggle.com/docs/api
- **Kernel Metadata Docs:** https://github.com/Kaggle/kaggle-api/blob/main/docs/kernels_metadata.md
- **Kernel Commands:** https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md

## Security Notes

- **Never commit `~/.kaggle/kaggle.json` to git** — add to `.gitignore`
- **Regenerate API keys** if accidentally exposed
- **Kaggle kernels are sandboxed** — safe to run untrusted code
- **GPU quota is per-account** — monitor usage at https://www.kaggle.com/settings/usage

---

**Last Updated:** 2026-03-26
**Status:** Ready for production
**Tested:** Kaggle CLI v1.5.13+
