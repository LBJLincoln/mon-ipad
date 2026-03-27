# Kaggle CLI Cheat Sheet

Quick reference for Kaggle command-line operations.

## Installation & Setup

```bash
# Install
pip install kaggle

# Setup credentials (one-time)
# 1. Go to https://www.kaggle.com/settings/account
# 2. Click "Create New Token"
# 3. Place file at ~/.kaggle/kaggle.json
mkdir -p ~/.kaggle
chmod 600 ~/.kaggle/kaggle.json

# Verify
kaggle competitions list --page-size 1
```

## Kernel Operations

### List Kernels

```bash
# All your kernels
kaggle kernels list -m

# Search by name
kaggle kernels list -m -s "nba"

# With pagination
kaggle kernels list -m --page 1 --page-size 10

# As CSV
kaggle kernels list -m -v

# Sort by date run
kaggle kernels list -m --sort-by dateRun

# Filter by competition
kaggle kernels list --competition house-prices --page-size 5
```

### Initialize Kernel

```bash
# Create metadata template
kaggle kernels init -p ./my_kernel

# Creates kernel-metadata.json with defaults
```

### Push Kernel (Upload & Auto-Run)

```bash
# Basic push
kaggle kernels push -p ./my_kernel

# With GPU (T4)
kaggle kernels push -p ./my_kernel --accelerator NvidiaTeslaT4

# With execution timeout (seconds)
kaggle kernels push -p ./my_kernel --timeout 7200

# Combined
kaggle kernels push -p ./my_kernel --accelerator NvidiaTeslaT4 --timeout 7200
```

### Check Kernel Status

```bash
# Current status
kaggle kernels status myusername/kernel-slug

# Returns: Status: queued | running | complete | failed

# In a loop every 60 seconds
while true; do
  kaggle kernels status myusername/my-kernel
  sleep 60
done
```

### Pull Kernel Source

```bash
# Download code only
kaggle kernels pull myusername/kernel-slug -p ./output

# With metadata
kaggle kernels pull myusername/kernel-slug -p ./output -m

# Into current directory
kaggle kernels pull myusername/kernel-slug -p .
```

### Download Kernel Output

```bash
# All files
kaggle kernels output myusername/kernel-slug -p ./output

# Only .json files
kaggle kernels output myusername/kernel-slug -p ./output --file-pattern ".*\.json$"

# Only .csv files
kaggle kernels output myusername/kernel-slug -p ./output --file-pattern ".*\.csv$"

# Overwrite existing
kaggle kernels output myusername/kernel-slug -p ./output -o

# Combine
kaggle kernels output myusername/kernel-slug -p ./output --file-pattern ".*\.json$" -o
```

### Delete Kernel

```bash
kaggle kernels delete myusername/kernel-slug
```

## Dataset Operations (Reference)

```bash
# List datasets
kaggle datasets list

# Download dataset
kaggle datasets download myusername/dataset-slug -p ./data

# Create dataset
kaggle datasets create -p ./dataset_folder

# Metadata for dataset
kaggle datasets metadata myusername/dataset-slug
```

## Competition Operations (Reference)

```bash
# List competitions
kaggle competitions list

# Download competition data
kaggle competitions download -c house-prices-advanced-regression-techniques -p ./data

# Submit to competition
kaggle competitions submit -c house-prices-advanced-regression-techniques -f submission.csv -m "My submission"
```

## Common Workflows

### Workflow 1: Push Notebook → Wait → Download

```bash
#!/bin/bash

USERNAME="myusername"
KERNEL_SLUG="my-notebook"
NOTEBOOK_PATH="./my_notebook.ipynb"

# 1. Init and setup
mkdir -p ./kernel_push
cp "$NOTEBOOK_PATH" ./kernel_push/

# 2. Create metadata
cat > ./kernel_push/kernel-metadata.json << EOF
{
  "id": "$USERNAME/$KERNEL_SLUG",
  "title": "My Notebook",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": false,
  "enable_gpu": true,
  "enable_internet": true,
  "code_file": "$(basename $NOTEBOOK_PATH)"
}
EOF

# 3. Push (auto-starts)
kaggle kernels push -p ./kernel_push --timeout 7200

# 4. Wait for completion (up to 3 hours)
START=$(date +%s)
TIMEOUT=$((3 * 60 * 60))

while true; do
  STATUS=$(kaggle kernels status "$USERNAME/$KERNEL_SLUG" | grep -o 'Status: [^ ]*' | cut -d' ' -f2)
  ELAPSED=$(($(date +%s) - START))

  echo "[$((ELAPSED / 60))m] Status: $STATUS"

  if [ "$STATUS" = "complete" ]; then
    echo "✓ Done!"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "✗ Kernel failed"
    exit 1
  elif [ "$ELAPSED" -gt "$TIMEOUT" ]; then
    echo "✗ Timeout"
    exit 1
  fi

  sleep 60
done

# 5. Download outputs
kaggle kernels output "$USERNAME/$KERNEL_SLUG" -p ./results -o
ls -lah ./results/
```

### Workflow 2: Monitor Running Kernel

```bash
#!/bin/bash

USERNAME="myusername"
KERNEL_SLUG="my-notebook"

# Check status every 30 seconds
for i in {1..120}; do
  STATUS=$(kaggle kernels status "$USERNAME/$KERNEL_SLUG" | grep -o 'Status: [^ ]*' | cut -d' ' -f2)
  echo "[$(date '+%H:%M:%S')] Status: $STATUS"

  if [ "$STATUS" = "complete" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 30
done

# Download when done
if [ "$STATUS" = "complete" ]; then
  kaggle kernels output "$USERNAME/$KERNEL_SLUG" -p ./results -o
fi
```

### Workflow 3: Update & Re-run Existing Kernel

```bash
# 1. Pull existing kernel
kaggle kernels pull myusername/my-kernel -p ./my_kernel -m

# 2. Edit the notebook
# ... edit ./my_kernel/my_notebook.ipynb ...

# 3. Re-push (updates existing kernel)
kaggle kernels push -p ./my_kernel --timeout 7200

# 4. Check status
kaggle kernels status myusername/my-kernel
```

### Workflow 4: Batch Download All Outputs

```bash
#!/bin/bash

USERNAME="myusername"

# Download outputs from all your recent kernels
kaggle kernels list -m --sort-by dateRun --page-size 5 | tail -n +2 | while read -r line; do
  KERNEL=$(echo "$line" | awk '{print $1}')
  echo "Downloading: $USERNAME/$KERNEL"
  kaggle kernels output "$USERNAME/$KERNEL" -p "./outputs/$KERNEL" -o 2>/dev/null || echo "  (may still be running)"
done
```

## Metadata File Reference

### Full kernel-metadata.json Example

```json
{
  "id": "myusername/my-kernel-slug",
  "id_no": 12345678,
  "title": "My Awesome Kernel",
  "author": "myusername",
  "description": "Description of what this kernel does",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": false,
  "enable_gpu": true,
  "enable_internet": true,
  "enable_internet_access": true,
  "code_file": "notebook.ipynb",
  "dataset_sources": [
    "username/dataset-slug",
    "another-user/another-dataset"
  ],
  "competition_sources": [
    "competition-slug"
  ],
  "kernel_sources": [
    "username/other-kernel"
  ],
  "model_sources": [
    "username/model:keras"
  ]
}
```

### Field Reference

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | string | required | Kernel identifier: "username/slug" |
| `id_no` | int | optional | Numeric kernel ID (alternative to `id`) |
| `title` | string | required | Human-readable title |
| `language` | string | required | python \| r \| rmarkdown |
| `kernel_type` | string | required | script \| notebook |
| `is_private` | boolean | true | true = private, false = public |
| `enable_gpu` | boolean | false | Enable GPU acceleration |
| `enable_internet` | boolean | false | Enable internet access (for pip) |
| `code_file` | string | required | Path to .ipynb or .py file |
| `dataset_sources` | array | [] | Linked datasets: ["user/dataset"] |
| `competition_sources` | array | [] | Linked competitions: ["comp-slug"] |
| `kernel_sources` | array | [] | Linked kernels: ["user/kernel"] |
| `model_sources` | array | [] | Linked models (complex format) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `HTTP 401 Unauthorized` | Check ~/.kaggle/kaggle.json, verify credentials at https://www.kaggle.com/settings/account |
| `Kernel not found` | Run `kaggle kernels list -m` to see exact slug format |
| `Notebook not found` | Verify `code_file` in metadata matches actual filename |
| `GPU not allocated` | Set `enable_gpu: true` in metadata, check quota at https://www.kaggle.com/settings/usage |
| `Status: unknown` | Kernel may not exist or slug is wrong. Run `kaggle kernels list -m` |
| `Output files empty` | Kernel may still be running. Check `kaggle kernels status ...` |
| `File permission denied` | Run `chmod 600 ~/.kaggle/kaggle.json` |

## Environment Variables (Optional)

```bash
# Override home directory for credentials
export KAGGLE_HOME=/custom/path
# Kaggle will look for ~/.kaggle/kaggle.json at /custom/path/kaggle.json

# Disable SSL verification (not recommended)
export KAGGLE_VERIFY_SSL=false
```

## Tips & Tricks

### Tip 1: Parse Status Output

```bash
STATUS=$(kaggle kernels status myusername/my-kernel | grep -o 'Status: [^ ]*' | cut -d' ' -f2)
if [ "$STATUS" = "complete" ]; then
  echo "Done!"
fi
```

### Tip 2: Set Default Username in Metadata

```bash
# Read from kaggle.json
USERNAME=$(python3 -c "import json; print(json.load(open('$HOME/.kaggle/kaggle.json'))['username'])")
echo $USERNAME
```

### Tip 3: Calculate Elapsed Time

```bash
START=$(date +%s)
# ... do stuff ...
ELAPSED=$(($(date +%s) - START))
echo "Elapsed: $((ELAPSED / 60)) minutes"
```

### Tip 4: Download Only Latest Outputs

```bash
KERNEL_SLUG="myusername/my-kernel"
LATEST_REF=$(kaggle kernels status "$KERNEL_SLUG" | grep ReferenceNumber | awk '{print $2}')
echo "Latest run reference: $LATEST_REF"
kaggle kernels output "$KERNEL_SLUG" -p ./outputs
```

### Tip 5: Run in Background with nohup

```bash
nohup bash -c 'kaggle kernels push -p ./kernel && \
  sleep 300 && \
  kaggle kernels output myusername/my-kernel -p ./results' > kernel.log 2>&1 &
```

## Performance Notes

- **T4 GPU:** ~15GB VRAM, ~1.3 TFLOPS
- **P100 GPU:** ~16GB VRAM, ~9.3 TFLOPS
- **Kernel timeout:** Default 3600s (1 hour), max 10800s (3 hours)
- **Execution limit:** Kernels can run up to 9 hours continuous (CPU)
- **Free quota:** 30 hours/week GPU access

## References

- Kaggle CLI GitHub: https://github.com/Kaggle/kaggle-cli
- Kaggle API Docs: https://www.kaggle.com/docs/api
- Kernel Metadata Wiki: https://github.com/Kaggle/kaggle-api/wiki/Kernel-Metadata
- Kernel Commands Docs: https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md

---

**Last Updated:** 2026-03-26
**CLI Version:** kaggle-cli 1.5.13+
