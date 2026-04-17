# Nomos42 — Brev Launchables

One-click GPU notebooks on NVIDIA Brev (free tier + Inception credits).
Every `.yaml` here is a Launchable config you can deploy via:

```bash
brev launch --config nomos42-karpathy.yaml
# or click the one-click link in the HF/Vercel dashboard
```

## Available

| File | GPU | Task | Free-tier fit |
|---|---|---|---|
| `nomos42-karpathy.yaml` | A10G or T4 | Karpathy autoresearch loop on the NBA fleet consensus | ✓ A10G on free trial |
| `nomos42-tabpfn-train.yaml` | H100 | TabPFN-2.5 walk-forward (186f, target Brier 0.21514) | ✗ requires DLI/Inception credits |

## How to use without CLI

1. Log in to https://brev.nvidia.com (NVIDIA developer account = same signup as build.nvidia.com)
2. "New Launchable" → "Import from URL" → paste the raw GitHub URL of the `.yaml`
3. Click "Launch" — notebook boots in ~90s with all our data mounted
4. The first cell kicks off the Karpathy loop; git-pushes results back to `mon-ipad` every iteration.

Secret required per launchable (set once in Brev's Secrets tab):
- `HF_TOKEN_3` (Nomos42 push token)
- `GITHUB_TOKEN` (for auto-push of results)
