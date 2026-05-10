#!/usr/bin/env python3
"""Apply Cycle 12 changes to paper.md (N12 fix: §4.6 + C.3.3).
Idempotent — no-op if already applied. Run from repo root."""
# v3 — git-native workflow commit

import sys

PAPER = "papers/axelrod-llm-2026/paper.md"

with open(PAPER, "r") as f:
    text = f.read()

# ── Change 1: §4.6 temperature note ──────────────────────────────────────────
OLD1 = (
    "in Appendix C.3.\n"
    "\n"
    "**Pre-registration.**"
)
NEW1 = (
    "in Appendix C.3. We note that for managed-inference APIs (T1–T11),\n"
    "the provider's instruction-following fine-tuning mediates the relationship\n"
    "between the API temperature parameter and token-logit variance, so the\n"
    "effective stochasticity at $\\tau = 0.7$ is provider-dependent.\n"
    "For self-hosted models (T12, Qwen3-4B-CPU), the parameter acts more\n"
    "directly on the logit distribution. The $\\tau = 0.7$ selection was\n"
    "validated on T4 (Gemini 3 Flash, \\textit{analytical} archetype);\n"
    "its transferability to self-hosted inference is treated as a limitation\n"
    "and flagged in Appendix C.3.3.\n"
    "\n"
    "**Pre-registration.**"
)

# ── Change 2: C.3.3 section ───────────────────────────────────────────────────
OLD2 = (
    "*conservative* may prefer $\\tau \\leq 0.5$; *devil's-advocate* may benefit from\n"
    "$\\tau \\geq 0.9$. Per-archetype temperature sweep deferred to future work.]**\n"
    "\n"
    "---\n"
    "\n"
    "## C.4"
)
NEW2 = (
    "*conservative* may prefer $\\tau \\leq 0.5$; *devil's-advocate* may benefit from\n"
    "$\\tau \\geq 0.9$. Per-archetype temperature sweep deferred to future work.]**\n"
    "\n"
    "### C.3.3  Limitation: Self-Hosted Model Temperature\n"
    "\n"
    "Two mechanisms cause managed-inference models to respond to $\\tau$ differently\n"
    "from self-hosted models. **(a) RLHF-induced sharpening:** instruction-following\n"
    "fine-tuning concentrates logit probability mass on alignment-consistent tokens\n"
    "[@ouyang2022training], narrowing the pre-softmax logit spread so that effective\n"
    "sample entropy at a given $\\tau$ is lower than for a base model of the same scale.\n"
    "**(b) Provider sampling pipeline:** managed APIs such as Gemini apply top-$k$ or\n"
    "nucleus top-$p$ filtering after temperature scaling; these cutoffs are proprietary\n"
    "and further constrain the output distribution beyond $\\tau$ alone.\n"
    "\n"
    "The self-hosted agent T12 (Qwen3-4B-CPU via llama.cpp) is subject to neither effect:\n"
    "temperature maps directly to the softmax inverse-temperature with no implicit top-$k$\n"
    "gate. Consequently $\\tau = 0.7$ may produce higher effective stochasticity for T12\n"
    "than for T4, potentially over-exploring the *disciplined* archetype's prediction space.\n"
    "A follow-up T12 temperature sweep is planned but lies outside the pre-registered protocol.\n"
    "\n"
    "---\n"
    "\n"
    "## C.4"
)

changed = False

if OLD1 in text:
    text = text.replace(OLD1, NEW1, 1)
    changed = True
    print("Applied: §4.6 temperature note")
elif NEW1 in text:
    print("Already applied: §4.6 temperature note")
else:
    print("ERROR: §4.6 target not found — aborting", file=sys.stderr)
    sys.exit(1)

if OLD2 in text:
    text = text.replace(OLD2, NEW2, 1)
    changed = True
    print("Applied: C.3.3 section")
elif NEW2 in text:
    print("Already applied: C.3.3 section")
else:
    print("ERROR: C.3.3 target not found — aborting", file=sys.stderr)
    sys.exit(1)

if changed:
    with open(PAPER, "w") as f:
        f.write(text)
    print(f"Written: {PAPER}")
else:
    print("No changes needed.")
