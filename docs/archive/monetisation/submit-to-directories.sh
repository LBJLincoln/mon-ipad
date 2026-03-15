#!/bin/bash
# Submit Nomos Multi-RAG to AI directories
# Run: bash monetisation/submit-to-directories.sh
# Most directories require manual form submission. This script opens URLs.

set -e

echo "=== Nomos Multi-RAG — Directory Submission Helper ==="
echo "Date: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo ""

# Copy-paste data for all forms
cat <<'DATA'
=========================================================
STANDARD SUBMISSION DATA — Copy for all forms
=========================================================

Name: Nomos Multi-RAG Orchestrator
Tagline: Production RAG system — 3 pipelines, 87.5% accuracy, $0 per query
URL: https://lbjlincoln.github.io/rag-dashboard/store.html
Demo: https://lbjlincoln-nomos-rag-engine.hf.space/healthz
Logo: (use screenshot of dashboard)
Category: Knowledge Retrieval / RAG / AI Agent
Pricing: Free tier (10 req/min, 100 req/day) + paid ($27-$497)
Contact: alexis.moret6@outlook.fr

Short Description (160 chars):
Production RAG with 3 pipelines: Standard (87.5%), Graph (Neo4j), Quantitative (SQL, 95.2%). Free inference. No API key. 61K eval questions.

Full Description:
Nomos Multi-RAG Orchestrator is a production-grade RAG system with 3 specialized pipelines. Standard Pipeline searches 46,263 vector embeddings (87.5% accuracy). Graph Pipeline traverses 79,451 Neo4j nodes. Quantitative Pipeline generates SQL over 40 PostgreSQL tables (95.2% accuracy). Free LLM inference via OpenRouter. No API key needed. Hosted on 9 HF Spaces. Tested on 61,661 questions from 18 SOTA benchmarks.

Tags: rag, retrieval, vector-search, graph-rag, sql-rag, neo4j, pinecone, supabase, n8n, free-llm, ai-agent
=========================================================
DATA

echo ""
echo "=== DIRECTORIES TO SUBMIT TO ==="
echo ""
echo "--- FREE DIRECTORIES (submit now) ---"
echo ""

URLS=(
  "https://aiagentsdirectory.com/submit-agent|AI Agents Directory (2,218 agents)"
  "https://aiagentslist.com/submit|AI Agents List (600+ agents)"
  "https://aiagentstore.ai/register|AI Agent Store"
  "https://submityouraitool.com|Submit Your AI Tool (free)"
  "https://aitoolsdirectory.com/submit-tool|AI Tools Directory"
  "https://aitools.inc/submit|AI Tools Inc"
  "https://www.insidr.ai/submit-tools/|Insidr.ai"
  "https://findmyaitool.com/submit-tool|Find My AI Tool"
  "https://www.dropyourai.com/submit-tool|DropYourAI"
  "https://aipediahub.com|AI Pedia Hub"
  "https://allthingsai.com|All Things AI"
  "https://www.futuretools.io|FutureTools.io"
  "https://coglist.com|CogList"
  "https://aiagentslive.com|AI Agents Live"
  "https://agenthunter.io|AgentHunter"
  "https://findyouragent.ai|FindYourAgent.ai"
  "https://trillionagent.com|TrillionAgent"
  "https://aiagentsverse.com|AI Agents Verse"
  "https://opentools.ai|OpenTools.ai"
  "https://agent.ai|Agent.ai"
)

for entry in "${URLS[@]}"; do
  IFS='|' read -r url name <<< "$entry"
  echo "  [ ] $name"
  echo "      URL: $url"
  echo ""
done

echo "--- MARKETPLACE (requires registration) ---"
echo ""
echo "  [ ] AgentX.Market"
echo "      URL: https://agentx.market/register"
echo ""
echo "  [ ] ClawdHub (OpenClaw)"
echo "      1. Sign in at https://clawhub.ai with GitHub"
echo "      2. Settings → API Tokens → Generate CLI token"
echo "      3. Run: export CLAWHUB_TOKEN='clh_xxx'"
echo "      4. Run: clawhub publish monetisation/clawhub-skills/nomos-rag-query --slug nomos-rag-query --version 1.0.0"
echo "      5. Run: clawhub publish monetisation/clawhub-skills/nomos-eval-framework --slug nomos-eval-framework --version 1.0.0"
echo "      6. Run: clawhub publish monetisation/clawhub-skills/nomos-debug-assistant --slug nomos-debug-assistant --version 1.0.0"
echo ""

echo "--- LAUNCH PLATFORMS ---"
echo ""
echo "  [ ] Product Hunt — https://www.producthunt.com (schedule for Tue/Wed)"
echo "  [ ] There's An AI For That — https://theresanaiforthat.com/submit/ (follow @theresanaiforthat for free monthly thread)"
echo ""

echo "--- EMAIL SUBMISSIONS ---"
echo ""
echo "  [ ] Add AI Directory — info@addaidirectory.com"
echo "      (see monetisation/submission-emails.md for template)"
echo ""

echo "--- ALREADY SUBMITTED ---"
echo ""
echo "  [x] LobeChat Agents — PR #1507: https://github.com/lobehub/lobe-chat-agents/pull/1507"
echo ""

echo "=== Total: 24 directories to submit ==="
echo "=== 1 already submitted (LobeChat) ==="
echo ""
echo "Pro tip: Open each URL in browser, paste the standard data above."
