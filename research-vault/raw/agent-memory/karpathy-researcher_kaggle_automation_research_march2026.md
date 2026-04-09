---
name: Kaggle Automation Research (March 2026)
description: Complete research on Kaggle CLI, MCP servers, API capabilities for direct GPU kernel management from Claude Code
type: reference
---

# Kaggle Automation Research — March 2026

## Executive Summary

Kaggle provides three pathways for direct automation from Claude Code on VM:

1. **Kaggle CLI** (native) — Official tool, mature, all operations via terminal
2. **Kaggle MCP Servers** — Two implementations for Claude Code integration
3. **Kaggle REST API** — Direct HTTP endpoints for programmatic control

**Recommendation:** Use **Kaggle CLI** for reliability + **Kaggle-MCP (54yyyu)** for Claude integration. CLI auto-pushes → starts kernel, but we can poll `kernels status` to monitor.

---

## 1. KAGGLE CLI SETUP & AUTHENTICATION

### Installation

```bash
pip install kaggle
```

Verify:
```bash
kaggle --help
```

### Authentication Setup

1. **Get API credentials:**
   - Visit https://www.kaggle.com/settings/account
   - Scroll to "API" section → "Create New Token"
   - Downloads `kaggle.json`

2. **Place credentials:**
   ```bash
   mkdir -p ~/.kaggle
   cp ~/Downloads/kaggle.json ~/.kaggle/
   chmod 600 ~/.kaggle/kaggle.json
   ```

3. **Verify:**
   ```bash
   kaggle competitions list  # Should work without errors
   ```

**Note:** File permissions `600` are mandatory. Kaggle enforces this check.

---

## 2. KAGGLE KERNELS OPERATIONS

### 2.1 Initialize Kernel Metadata

Before pushing, create a template:

```bash
mkdir nba_gpu_kernel
cd nba_gpu_kernel
kaggle kernels init -p .
```

Generates `kernel-metadata.json`:

```json
{
  "title": "My Kernel",
  "id": "username/kernel-slug",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": false,
  "enable_internet": false,
  "code_file": "code.ipynb"
}
```

### 2.2 Kernel Metadata Configuration

**Required fields:**
- `id` (slug format: "username/kernel-slug") OR `id_no` (numeric)
- `code_file` — path to .ipynb or .py relative to metadata
- `language` — `python`, `r`, or `rmarkdown`
- `kernel_type` — `script` or `notebook`
- `title` — name (required for new kernels)

**Optional fields:**
- `is_private` (bool, default=true)
- `enable_gpu` (bool, default=false) — **We want true!**
- `enable_internet` (bool, default=false) — **We want true for dependencies!**
- `dataset_sources` (list: ["username/dataset-slug", ...])
- `competition_sources` (list: ["competition-slug", ...])
- `kernel_sources` (list: ["username/kernel-slug", ...])
- `model_sources` (list with detailed specs)

### 2.3 Push Kernel → Auto-run

```bash
# Basic push (auto-runs after upload)
kaggle kernels push -p /path/to/kernel

# With GPU T4
kaggle kernels push -p /path/to/kernel --accelerator NvidiaTeslaT4

# With timeout (seconds)
kaggle kernels push -p /path/to/kernel --timeout 3600
```

**IMPORTANT:** Push **automatically** triggers execution. After push, kernel goes into queue.

### 2.4 Check Kernel Status

```bash
kaggle kernels status username/kernel-slug
```

Output example:
```
Status: complete
ReferenceNumber: 12345678
```

Status values: `queued`, `running`, `complete`, `failed`, `committing`

### 2.5 Download Kernel Output Files

```bash
# All output files
kaggle kernels output username/kernel-slug -p ./output

# Specific files (regex pattern)
kaggle kernels output username/kernel-slug -p ./output --file-pattern ".*\.json$"

# Force overwrite
kaggle kernels output username/kernel-slug -p ./output -o
```

### 2.6 Pull Kernel Code + Metadata

```bash
# Code only
kaggle kernels pull username/kernel-slug -p ./local_kernel

# With metadata
kaggle kernels pull username/kernel-slug -p ./local_kernel -m
```

### 2.7 List Your Kernels

```bash
# All your kernels
kaggle kernels list -m

# Search by name
kaggle kernels list -m -s "nba"

# Filter by competition
kaggle kernels list --competition house-prices-advanced-regression-techniques --page-size 5

# Sort by date run
kaggle kernels list -m --sort-by dateRun

# CSV output
kaggle kernels list -m -v
```

---

## 3. KAGGLE MCP SERVERS FOR CLAUDE CODE

### Option A: 54yyyu/kaggle-mcp (Community-Maintained)

**GitHub:** https://github.com/54yyyu/kaggle-mcp

**Features:**
- Competitions: Browse, search, download data
- Datasets: Find, explore, download
- Kernels: Search and analyze notebooks
- Models: Access pre-trained models

**Setup:**

macOS/Linux:
```bash
curl -LsSf https://raw.githubusercontent.com/54yyyu/kaggle-mcp/main/install.sh | sh
```

Windows:
```powershell
powershell -c "Invoke-WebRequest -Uri https://raw.githubusercontent.com/54yyyu/kaggle-mcp/main/install.ps1 -OutFile install.ps1; .\install.ps1"
```

**Configure Claude Desktop:**

Edit `~/.config/claude.json` or `~/Library/Application Support/Claude/claude.json`:

```json
{
  "mcpServers": {
    "kaggle": {
      "command": "kaggle-mcp"
    }
  }
}
```

**Credentials:**
1. Place `~/.kaggle/kaggle.json` from earlier
2. Or run `kaggle-mcp-setup` to prompt for username + API key

### Option B: KrishnaPramodParupudi/kaggle-mcp-server

**GitHub:** https://github.com/KrishnaPramodParupudi/kaggle-mcp-server

Similar setup, focuses on competitions. Lighter weight.

### Option C: Composio Kaggle Toolkit (Third-party)

**URL:** https://composio.dev/toolkits/kaggle/framework/claude-code

**Features via Composio (declarative, tool-routed):**
- Dataset management (create, version, list files)
- Competition operations (download data, submit entries)
- Kernel management (initialize, download outputs, monitor status)
- Configuration management

**Advantage:** Single MCP endpoint, dynamic tool loading.

---

## 4. KAGGLE REST API (Direct HTTP)

### Base URL & Auth

```
https://www.kaggle.com/api/v1
Authorization: Basic <base64(username:api_token)>
```

Example:
```bash
curl -u "username:api_token" https://www.kaggle.com/api/v1/kernels/list
```

### Key Endpoints

#### List Kernels
```
GET /kernels
  ?creatorRef=<username>
  &pageSize=<int>
  &sortBy=<hotness|dateRun|viewCount|etc>
```

#### Get Kernel Details
```
GET /kernels/{kernel_id_or_slug}
```

Returns:
```json
{
  "id": 12345678,
  "slug": "username/kernel-slug",
  "ref": "username/kernel-slug",
  "title": "...",
  "author": "...",
  "lastRunTime": "2026-03-26T14:30:00.000Z",
  "currentStatus": "complete",
  "totalRunCount": 5,
  "language": "python"
}
```

#### Create/Update Kernel
```
POST /kernels/push
Content-Type: application/json

{
  "id": "username/kernel-slug",
  "title": "...",
  "language": "python",
  "kernel_type": "notebook",
  "code": "<ipynb_json_blob>",
  "enable_gpu": true,
  "enable_internet": true
}
```

#### Get Kernel Status
```
GET /kernels/{kernel_slug}/getStatus
```

Returns:
```json
{
  "status": "complete",
  "referenceNumber": 12345678
}
```

#### Download Kernel Output
```
GET /kernels/{kernel_slug}/output
```

Returns a zip of all output files.

---

## 5. PYTHON AUTOMATION SCRIPT TEMPLATE

### Using Kaggle CLI via subprocess

```python
import subprocess
import time
import json
from pathlib import Path

class KaggleKernelManager:
    def __init__(self, username, kernel_slug):
        self.username = username
        self.kernel_slug = kernel_slug
        self.full_id = f"{username}/{kernel_slug}"

    def push_and_run(self, kernel_path, enable_gpu=True, timeout_seconds=3600):
        """Push kernel and auto-start execution."""
        # Update metadata
        metadata_file = Path(kernel_path) / "kernel-metadata.json"
        metadata = {
            "id": self.full_id,
            "title": f"NBA GPU Evolution {self.kernel_slug}",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": False,
            "enable_gpu": enable_gpu,
            "enable_internet": True,
            "code_file": "nba_gpu_v2.ipynb"
        }

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Push (auto-starts)
        cmd = ["kaggle", "kernels", "push", "-p", str(kernel_path)]
        if timeout_seconds:
            cmd.extend(["--timeout", str(timeout_seconds)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Push failed: {result.stderr}")

        print(f"Kernel {self.full_id} pushed and running")
        return True

    def wait_for_completion(self, max_wait_minutes=180, poll_interval_seconds=30):
        """Poll status until complete or timeout."""
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60

        while time.time() - start_time < max_wait_seconds:
            status = self.get_status()
            print(f"[{int((time.time() - start_time)/60)}m] Status: {status}")

            if status == "complete":
                print("✓ Kernel completed successfully")
                return True
            elif status == "failed":
                print("✗ Kernel failed")
                return False

            time.sleep(poll_interval_seconds)

        print("✗ Timeout waiting for completion")
        return False

    def get_status(self):
        """Get current kernel status."""
        cmd = ["kaggle", "kernels", "status", self.full_id]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return "unknown"

        # Parse output: "Status: complete"
        for line in result.stdout.split('\n'):
            if line.startswith("Status:"):
                return line.split(":")[-1].strip().lower()

        return "unknown"

    def download_outputs(self, output_dir="./kaggle_output"):
        """Download all output files."""
        cmd = ["kaggle", "kernels", "output", self.full_id, "-p", output_dir, "-o"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Output download failed: {result.stderr}")

        print(f"Outputs downloaded to {output_dir}")
        return output_dir

# Usage
if __name__ == "__main__":
    mgr = KaggleKernelManager("myusername", "nba-quant-gpu-v2")

    # Push with GPU
    mgr.push_and_run("/path/to/kernel/folder", enable_gpu=True, timeout_seconds=3600)

    # Wait for completion (up to 3 hours)
    if mgr.wait_for_completion(max_wait_minutes=180, poll_interval_seconds=60):
        # Download results
        mgr.download_outputs("./results")
        print("Complete! Results ready in ./results")
    else:
        print("Kernel did not complete")
```

### Using Python KaggleApi Class (Legacy)

```python
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

# Push kernel
api.kernels_push("myusername", "my-kernel", "path/to/kernel")

# Get status
status = api.kernels_status("myusername/my-kernel")
print(status)

# Download output
api.kernels_output("myusername/my-kernel", "path/to/download")
```

---

## 6. WORKFLOW: PUSH → MONITOR → PULL

### Manual CLI Workflow

```bash
# 1. Initialize
mkdir nba_gpu_v2_kernel
kaggle kernels init -p nba_gpu_v2_kernel

# 2. Edit metadata
cat > nba_gpu_v2_kernel/kernel-metadata.json << 'EOF'
{
  "id": "myusername/nba-quant-gpu-v2",
  "title": "NBA Quant GPU Evolution v2",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": false,
  "enable_gpu": true,
  "enable_internet": true,
  "code_file": "nba_gpu_v2.ipynb"
}
EOF

# 3. Copy notebook
cp ~/nomos-nba-agent/colab/nba_gpu_v2.ipynb nba_gpu_v2_kernel/

# 4. Push (auto-runs)
kaggle kernels push -p nba_gpu_v2_kernel --timeout 7200

# 5. Monitor (loop every 60s)
for i in {1..180}; do
  kaggle kernels status myusername/nba-quant-gpu-v2
  sleep 60
done

# 6. Download outputs
kaggle kernels output myusername/nba-quant-gpu-v2 -p ./results -o

# 7. Check files
ls -lah results/
```

### Automated Python Workflow

See **Section 5** template above.

---

## 7. ADVANTAGES & LIMITATIONS

### Kaggle CLI Advantages

✓ Official, mature, well-documented
✓ No dependencies beyond `pip install kaggle`
✓ Works in any terminal/VM environment
✓ Reliable status polling
✓ GPU acceleration included (T4 in free tier)
✓ 30 hours/week free P100/2xT4 (if account works)

### Kaggle CLI Limitations

✗ Auto-runs after push (can't schedule separately)
✗ No real-time kernel logs (only final output)
✗ Kernel status limited to: queued, running, complete, failed
✗ Account stability issues reported (as noted in CLAUDE.md)

### MCP Servers Advantages

✓ Native Claude Code integration
✓ Declarative tool interface
✓ Better for exploring/querying (no raw CLI parsing)

### MCP Servers Limitations

✗ Cannot start kernels directly (kaggle-mcp designed for read/search)
✗ Additional setup/dependencies

---

## 8. RECOMMENDED SETUP FOR NOMOS42

### Architecture

```
mon-ipad VM (Claude Code)
    ↓
  [Python script using Kaggle CLI]
    ↓
  Kaggle Account (myusername)
    ↓
  GPU Kernel (nba-quant-gpu-v2)
    ↓ (push → auto-run)
  Kaggle Servers (T4 GPU)
    ↓ (monitor via status)
  [Polling loop: wait for "complete"]
    ↓
  [Download outputs via CLI]
    ↓
  ~/results/ (on VM)
    ↓ (parse + push to git)
  mon-ipad repo (data/, results/, analysis/)
```

### Implementation Checklist

- [ ] **Install Kaggle CLI:** `pip install kaggle`
- [ ] **Auth:** Create `~/.kaggle/kaggle.json` with API credentials from https://www.kaggle.com/settings/account
- [ ] **Permissions:** `chmod 600 ~/.kaggle/kaggle.json`
- [ ] **Test:** `kaggle kernels list -m` (should list your kernels)
- [ ] **Prepare notebook:** Copy `nba_gpu_v2.ipynb` to kernel folder
- [ ] **Create metadata:** `kernel-metadata.json` with enable_gpu=true, enable_internet=true
- [ ] **Create manager script:** `scripts/kaggle_kernel_manager.py` (template in Section 5)
- [ ] **Integrate into cron:** Add to `autonomous-cycle.sh` or new `kaggle-gpu-evolution.sh`
- [ ] **Monitor:** Polling loop with exponential backoff (30s → 60s → 120s as timeout increases)
- [ ] **Pull results:** Auto-download outputs and parse metrics
- [ ] **Push to git:** Commit results + log to data/agent-activity.json

### Sample Cron Integration

```bash
# scripts/kaggle-gpu-evolution.sh

#!/bin/bash
set -e

cd /home/termius/mon-ipad

# Activate venv
source venv/bin/activate

# Run GPU evolution via Kaggle kernel
python3 scripts/kaggle_kernel_manager.py \
  --username myusername \
  --kernel-slug nba-quant-gpu-v2 \
  --notebook-path ~/nomos-nba-agent/colab/nba_gpu_v2.ipynb \
  --timeout-minutes 120 \
  --output-dir ./data/kaggle_results \
  --wait-for-completion \
  --max-wait-minutes 180

# Parse results + commit
if [ -f "./data/kaggle_results/best_model.json" ]; then
  git add data/kaggle_results/
  git commit -m "data: kaggle gpu evolution $(date +%Y-%m-%d)"
  git push origin main
fi
```

---

## 9. TROUBLESHOOTING

### "Kernel not found"

**Cause:** Metadata `id` field doesn't match username/slug format.

**Fix:**
```json
{
  "id": "myusername/my-kernel-slug",  // NOT "my-kernel-slug" alone
  "title": "..."
}
```

### "credentials not found"

**Cause:** `~/.kaggle/kaggle.json` missing or wrong permissions.

**Fix:**
```bash
cat ~/.kaggle/kaggle.json  # Verify file exists
chmod 600 ~/.kaggle/kaggle.json
```

### "Kernel push error: Notebook not found"

**Cause:** `code_file` path incorrect in metadata.

**Fix:**
```bash
cd /path/to/kernel
ls -la  # Verify notebook file exists
# Update metadata code_file to match actual filename
```

### "Status: unknown"

**Cause:** Kernel doesn't exist or wrong slug.

**Fix:**
```bash
kaggle kernels list -m  # List your kernels
# Copy exact slug from output
```

### GPU not allocated

**Cause:** `enable_gpu: false` in metadata or quota exceeded.

**Fix:**
```json
{
  "enable_gpu": true,
  "accelerator": "NvidiaTeslaT4"  // Optional, specify T4
}
```

Check quota: https://www.kaggle.com/settings/usage

---

## 10. REFERENCES

### Official Documentation

- Kaggle CLI: https://github.com/Kaggle/kaggle-cli
- Kaggle API: https://www.kaggle.com/docs/api
- Kernel Metadata: https://github.com/Kaggle/kaggle-api/blob/main/docs/kernels_metadata.md
- Kernel Commands: https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md

### MCP Servers

- Kaggle-MCP (54yyyu): https://github.com/54yyyu/kaggle-mcp
- Kaggle-MCP Server: https://github.com/KrishnaPramodParupudi/kaggle-mcp-server
- Composio Kaggle: https://composio.dev/toolkits/kaggle/framework/claude-code

### REST API

- Public API docs: https://www.kaggle.com/docs/api
- REST examples: https://documenter.getpostman.com/view/7523144/T1LTejEQ

---

## 11. CRITICAL NOTE ON NOMOS42 ACCOUNT STATUS

From CLAUDE.md feedback:

> **Kaggle BROKEN** — account issues, use Google Colab instead

**However**, this research shows:

1. If account is re-enabled or new account created → Kaggle CLI/MCP is production-ready
2. Colab remains primary (proven T4 access, Drive persistence with v2 notebook)
3. Kaggle is **backup** with better quota (30hr/week vs Colab 4-12h sessions)

**Action:** Verify Kaggle account status before implementing. If 401/403, use Colab v2 or Modal/Lightning alternatives instead.

---

**Last Updated:** 2026-03-26
**Status:** Ready for implementation
**Effort to integrate:** 4-6 hours (script + testing + cron integration)
