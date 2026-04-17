---
title: Fin-R1-7B CPU
emoji: 💹
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Finance-pretrained 7B reasoning LLM (Qwen2.5 + Fin-R1 CoT)
---

# Fin-R1-7B CPU (Nomos42)

OpenAI-compatible CPU endpoint for **Fin-R1** (SUFE-AIFLM-Lab, arXiv 2503.16252).

**Base:** Qwen2.5-7B + Fin-R1-Data (60k finance CoT) + GRPO-RL
**Benchmarks:** FinQA 76.0 | ConvFinQA 85.0 | FinanceIQ 73.3 (matches DeepSeek-R1 at 7B)
**Quantization:** Q4_K_M (~4.5 GB) via mradermacher
**License:** Apache 2.0

## Usage

```bash
curl -X POST https://nomos42-fin-r1-7b-cpu.hf.space/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"fin-r1-7b","messages":[{"role":"user","content":"NVDA PE ratio analysis?"}]}'
```

## Role in Nomos42 fleet

Replaces T15 selfhost-gemma3 on POL Trading Floor (political-economy reasoning),
then deployed as analyst on D8 Finance council.

Context: 4096 tokens (reasoning headroom) | Throughput: ~6-9 tok/s on 2vCPU.
