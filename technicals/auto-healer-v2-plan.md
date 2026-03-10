# Auto-Healer V2.0 Upgrade Plan

> Created: 2026-03-10
> Status: PLAN ONLY — do NOT modify workflow JSON until approved
> Current: V1.0 at `/home/termius/mon-ipad/n8n/live/auto-healer.json`

---

## 1. Current V1.0 Architecture

```
Every 30min / Manual Webhook
  → Init Config & Targets (20 smoke questions, 4 pipeline configs, 4 n8n hosts)
  → Fetch Execution Health (10 recent execs per pipeline via REST API)
  → Run Smoke Tests (5 random questions, round-robin across hosts, keyword scoring)
  → LLM Analyze & Propose Patch (llama-70b, structured JSON, single patch proposal)
  → Build Structured Report (health + smoke + patch + gaps)
  → Format for Delivery (human-readable summary)
  → Store Report (static data, last 50) + Respond to Trigger

GET /webhook/auto-healer-results → Serve Last Report
```

### V1.0 Limitations

| Area | Current | Problem |
|------|---------|---------|
| Smoke tests | 5 random questions | Not statistically significant; misses pipeline-specific failures |
| Execution analysis | Last 10 executions, simple success/error count | No error categorization, no response quality analysis |
| Metrics | Overall score + per-sector average | No latency trends, no citation tracking, no source quality |
| LLM analysis | Single prompt, single patch | No multi-turn reasoning, no historical context, no A/B comparison |
| CLI output | Flat JSON report | Hard to parse, no actionable ranking, no risk scoring |
| History | Static data (volatile, lost on rebuild) | No persistent trend tracking, no regression detection |

---

## 2. V2.0 Target Architecture

```
Every 15min / Manual Webhook
  → Init Config V2 (targets, history, 40 test questions)
  → PARALLEL:
  │   ├─ Fetch Execution Analytics (ALL recent execs, error categorization)
  │   ├─ Run Comprehensive Tests (20 questions, ALL 4 pipelines, quality scoring)
  │   └─ Fetch Previous Metrics (from Supabase for trend comparison)
  │
  → Aggregate Metrics (per-pipeline, per-sector, trends)
  → LLM Deep Analysis (historical context, multi-factor, ranked proposals)
  → Build Dashboard Data (structured for CLI consumption)
  → PARALLEL:
  │   ├─ Store to Supabase (persistent history)
  │   ├─ Store to Static Data (fast cache)
  │   └─ Respond to Trigger
  │
GET /webhook/auto-healer-results → Serve Dashboard + History
GET /webhook/auto-healer-history?days=7 → Serve Trend Data
```

---

## 3. Upgrade Details by Component

### 3.1 Execution Analytics (replaces `Fetch Execution Health`)

**Current**: Fetches 10 recent executions per pipeline, counts success/error.

**V2.0**: Fetch 50 executions per pipeline, deep-analyze each one.

```javascript
// ─── Execution Analytics V2 ───
// For each pipeline, fetch last 50 executions and categorize

const ANALYTICS_PER_PIPELINE = 50;

for (const [wfId, pipeline] of Object.entries(config.pipelines)) {
  // Fetch executions
  const resp = await fetch(
    `${host}/rest/executions?limit=${ANALYTICS_PER_PIPELINE}&workflowId=${wfId}`,
    { headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(20000) }
  );
  const data = await resp.json();
  const execs = data.data?.results || data.data || [];

  // Categorize errors
  const errorCategories = {};
  const latencies = [];
  let successCount = 0;
  let errorCount = 0;
  let lastSuccess = null;
  let lastError = null;

  for (const exec of execs) {
    const duration = exec.startedAt && exec.stoppedAt
      ? new Date(exec.stoppedAt) - new Date(exec.startedAt) : null;

    if (exec.status === 'success') {
      successCount++;
      if (duration) latencies.push(duration);
      if (!lastSuccess) lastSuccess = exec.stoppedAt;
    } else if (exec.status === 'error') {
      errorCount++;
      if (!lastError) lastError = exec.stoppedAt;

      // Categorize error by examining execution data
      const errorType = categorizeError(exec);
      errorCategories[errorType] = (errorCategories[errorType] || 0) + 1;
    }
  }

  // Calculate percentiles
  latencies.sort((a, b) => a - b);
  const p50 = latencies[Math.floor(latencies.length * 0.5)] || 0;
  const p95 = latencies[Math.floor(latencies.length * 0.95)] || 0;
  const p99 = latencies[Math.floor(latencies.length * 0.99)] || 0;

  results.push({
    pipeline: pipeline.name,
    workflow_id: wfId,
    total_analyzed: execs.length,
    success_rate: Math.round(successCount / Math.max(execs.length, 1) * 100),
    error_distribution: errorCategories,
    latency: { p50, p95, p99, avg: Math.round(latencies.reduce((s,v) => s+v, 0) / Math.max(latencies.length, 1)) },
    last_success: lastSuccess,
    last_error: lastError,
    health_status: errorCount > execs.length * 0.5 ? 'CRITICAL'
      : errorCount > execs.length * 0.2 ? 'UNHEALTHY'
      : errorCount > execs.length * 0.1 ? 'DEGRADED'
      : 'HEALTHY'
  });
}
```

**Error categorization function** (new):
```javascript
function categorizeError(exec) {
  const errorMsg = (exec.data?.resultData?.error?.message || '').toLowerCase();
  if (errorMsg.includes('timeout') || errorMsg.includes('timed out')) return 'TIMEOUT';
  if (errorMsg.includes('429') || errorMsg.includes('rate limit')) return 'RATE_LIMIT';
  if (errorMsg.includes('500') || errorMsg.includes('internal')) return 'UPSTREAM_500';
  if (errorMsg.includes('connection') || errorMsg.includes('econnrefused')) return 'CONNECTION';
  if (errorMsg.includes('pinecone') || errorMsg.includes('vector')) return 'PINECONE';
  if (errorMsg.includes('embedding') || errorMsg.includes('jina')) return 'EMBEDDING';
  if (errorMsg.includes('llm') || errorMsg.includes('litellm')) return 'LLM';
  if (errorMsg.includes('postgres') || errorMsg.includes('bm25')) return 'DATABASE';
  return 'UNKNOWN';
}
```

### 3.2 Comprehensive Testing (replaces `Run Smoke Tests (5q)`)

**Current**: 5 random questions, Standard pipeline only, keyword matching.

**V2.0**: 20 questions (5/sector), test ALL 4 pipelines, quality scoring.

**Changes**:

1. **Test all 4 pipelines** (not just Standard):
   - Standard: 5 questions (1/sector + 1 random)
   - Graph: 3 questions (focus on relationship queries)
   - Quant: 2 questions (finance-specific)
   - Orchestrator: 5 questions (should auto-route correctly)

2. **Quality scoring** beyond keyword match:
```javascript
function scoreResponse(response, test) {
  const answer = (response.response || response.answer || '').toLowerCase();

  // 1. Keyword coverage (existing, weight 30%)
  const kwMatched = test.expected_keywords.filter(kw => answer.includes(kw.toLowerCase()));
  const kwScore = kwMatched.length / test.expected_keywords.length;

  // 2. Source citation (weight 20%)
  const sources = response.sources || [];
  const hasSources = sources.length > 0;
  const sourceScore = hasSources ? Math.min(sources.length / 3, 1.0) : 0;

  // 3. Language match (weight 20%)
  const questionLang = detectLanguage(test.q);
  const answerLang = detectLanguage(answer);
  const langScore = questionLang === answerLang ? 1.0 : 0;

  // 4. Response length quality (weight 15%)
  // Too short = no info, too long = hallucination
  const len = answer.length;
  const lenScore = len < 20 ? 0 : len < 50 ? 0.3 : len < 500 ? 1.0 : len < 1000 ? 0.8 : 0.5;

  // 5. Sector relevance (weight 15%)
  const sectorTerms = SECTOR_VOCABULARY[test.sector] || [];
  const sectorMatches = sectorTerms.filter(t => answer.includes(t.toLowerCase()));
  const sectorScore = Math.min(sectorMatches.length / 3, 1.0);

  return {
    total: Math.round((kwScore * 0.30 + sourceScore * 0.20 + langScore * 0.20 + lenScore * 0.15 + sectorScore * 0.15) * 100),
    keyword: Math.round(kwScore * 100),
    citation: Math.round(sourceScore * 100),
    language: Math.round(langScore * 100),
    length: Math.round(lenScore * 100),
    sector_relevance: Math.round(sectorScore * 100)
  };
}
```

3. **Sector vocabulary** for relevance detection:
```javascript
const SECTOR_VOCABULARY = {
  finance: ['bilan', 'actif', 'passif', 'trésorerie', 'dette', 'capital', 'ratio',
            'amortissement', 'provision', 'consolidation', 'IFRS', 'PCG', 'cash-flow'],
  btp: ['chantier', 'béton', 'armature', 'fondation', 'DTU', 'Eurocode', 'NF',
        'lot', 'ouvrage', 'maître', 'plancher', 'isolation', 'CCTP', 'RE2020'],
  juridique: ['article', 'code', 'loi', 'décret', 'tribunal', 'juge', 'assignation',
              'contrat', 'clause', 'responsabilité', 'prescription', 'juridiction'],
  industrie: ['processus', 'qualité', 'ISO', 'norme', 'maintenance', 'défaillance',
              'calibrage', 'tolérance', 'conformité', 'audit', 'AMDEC', 'lean']
};
```

### 3.3 Metrics Dashboard Data (NEW node)

**Purpose**: Produce structured metrics that the CLI can render as a dashboard.

```javascript
// ─── Aggregate Metrics V2 ───
const execAnalytics = $node['Execution Analytics V2'].json;
const testResults = $node['Comprehensive Tests'].json;
const previousMetrics = $node['Fetch Previous Metrics'].json;

const dashboard = {
  timestamp: new Date().toISOString(),
  run_id: config.run_id,

  // Per-pipeline metrics
  pipelines: Object.entries(config.pipelines).map(([wfId, pipeline]) => {
    const exec = execAnalytics.find(e => e.workflow_id === wfId) || {};
    const tests = testResults.filter(t => t.pipeline === pipeline.name);

    return {
      name: pipeline.name,
      workflow_id: wfId,
      health: exec.health_status || 'UNKNOWN',
      success_rate: exec.success_rate || 0,
      latency: exec.latency || {},
      error_count: Object.values(exec.error_distribution || {}).reduce((s,v) => s+v, 0),
      error_types: exec.error_distribution || {},
      last_success: exec.last_success,
      test_score: tests.length > 0
        ? Math.round(tests.reduce((s, t) => s + t.score.total, 0) / tests.length)
        : null
    };
  }),

  // Per-sector metrics
  sectors: ['finance', 'btp', 'juridique', 'industrie'].map(sector => {
    const sectorTests = testResults.filter(t => t.sector === sector);
    const target = { finance: 90, btp: 85, juridique: 90, industrie: 85 }[sector];
    const current = sectorTests.length > 0
      ? Math.round(sectorTests.reduce((s, t) => s + t.score.total, 0) / sectorTests.length)
      : 0;

    return {
      name: sector,
      current_score: current,
      target_score: target,
      gap: target - current,
      on_track: current >= target * 0.9,  // within 10% of target
      query_count: sectorTests.length,
      avg_citation_rate: Math.round(
        sectorTests.reduce((s, t) => s + t.score.citation, 0) / Math.max(sectorTests.length, 1)
      ),
      avg_language_match: Math.round(
        sectorTests.reduce((s, t) => s + t.score.language, 0) / Math.max(sectorTests.length, 1)
      ),
      avg_sector_relevance: Math.round(
        sectorTests.reduce((s, t) => s + t.score.sector_relevance, 0) / Math.max(sectorTests.length, 1)
      )
    };
  }),

  // Trends (vs previous run)
  trends: previousMetrics ? {
    overall_delta: currentOverall - (previousMetrics.overall_score || 0),
    sector_deltas: ['finance', 'btp', 'juridique', 'industrie'].map(s => ({
      sector: s,
      previous: previousMetrics.sector_scores?.[s] || 0,
      current: currentSectorScores[s] || 0,
      delta: (currentSectorScores[s] || 0) - (previousMetrics.sector_scores?.[s] || 0)
    })),
    latency_delta: currentAvgLatency - (previousMetrics.avg_latency || 0),
    improving: currentOverall > (previousMetrics.overall_score || 0)
  } : null,

  // Summary flags for quick CLI rendering
  flags: {
    any_pipeline_down: execAnalytics.some(e => e.health_status === 'CRITICAL'),
    any_pipeline_degraded: execAnalytics.some(e => e.health_status === 'DEGRADED' || e.health_status === 'UNHEALTHY'),
    worst_sector: worstSector.name,
    worst_sector_gap: worstSector.gap,
    needs_attention: worstSector.gap > 20
  }
};
```

### 3.4 Smarter LLM Analysis (replaces `LLM Analyze & Propose Patch`)

**Current**: Single LLM call, single patch, no history.

**V2.0**: Multi-factor analysis with historical context and ranked proposals.

**System prompt changes**:

```
You are an expert n8n RAG pipeline optimizer analyzing a production system with 4 sector-specific pipelines.

You have access to:
1. EXECUTION ANALYTICS: Success rates, error distributions, latency percentiles per pipeline
2. QUALITY METRICS: Per-question scores broken down by keyword coverage, source citation, language match, sector relevance
3. HISTORICAL TRENDS: Comparison with the last 5 runs showing improvement/regression
4. SECTOR TARGETS: Finance >=90%, BTP >=85%, Juridique >=90%, Industrie >=85%

You MUST respond in valid JSON with this schema:
{
  "executive_summary": "2-3 sentence overall assessment",
  "system_health": "GREEN|YELLOW|RED",

  "analysis": {
    "pattern_detected": "describe the dominant failure pattern",
    "root_cause": "specific technical root cause",
    "affected_scope": "which sectors/pipelines/query types"
  },

  "proposals": [
    {
      "id": 1,
      "priority": "P0|P1|P2|P3",
      "title": "short title",
      "target_pipeline": "Standard|Graph|Quant|Orchestrator|ALL",
      "improvement_type": "prompt_change|param_tweak|node_config|retrieval_change|error_handling|data_quality",
      "specific_change": {
        "node_name": "exact node name",
        "field": "parameter to change",
        "current_value_summary": "what is there now",
        "new_value": "the exact new value",
        "rationale": "why this helps"
      },
      "expected_impact": "+X% on sector Y",
      "confidence": 0.0-1.0,
      "risk": "LOW|MEDIUM|HIGH",
      "rollback": "how to undo",
      "dependencies": "what must be true for this to work",
      "estimated_effort": "minutes to implement"
    }
  ],

  "data_quality_issues": [
    "list any data-level problems detected (missing sectors, stale docs, etc.)"
  ],

  "next_eval_focus": "which sector/pipeline should the next eval cycle prioritize"
}

Rules:
- Propose 1-3 changes, ranked by impact/risk ratio
- P0 = pipeline down (fix immediately), P1 = major accuracy gap, P2 = moderate improvement, P3 = optimization
- Always include rollback instructions
- If trends show regression, flag it prominently
- If everything is healthy, still propose the highest-value optimization
- Consider data quality issues (not just pipeline logic)
- Reference specific test results and error patterns in your analysis
```

**User prompt changes**: Include historical trend data in the prompt:

```
EXECUTION ANALYTICS (last 50 per pipeline):
{execAnalytics JSON}

QUALITY TEST RESULTS (20 questions across 4 pipelines):
{testResults JSON with per-question scoring breakdown}

HISTORICAL TRENDS (last 5 runs):
{trendData JSON}

SECTOR SCORE GAPS:
{gaps JSON showing current vs target per sector}

ERROR DISTRIBUTION SUMMARY:
{errorSummary JSON}
```

### 3.5 Persistent Storage (NEW — Supabase)

**Current**: Static data in n8n (volatile, lost on Space rebuild).

**V2.0**: Store metrics in Supabase for persistence and trend analysis.

**New table**: `auto_healer_runs`

```sql
CREATE TABLE auto_healer_runs (
  id SERIAL PRIMARY KEY,
  run_id TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  overall_score INTEGER,
  sector_scores JSONB,
  pipeline_health JSONB,
  test_results JSONB,
  llm_proposals JSONB,
  execution_analytics JSONB,
  flags JSONB
);

CREATE INDEX idx_auto_healer_created ON auto_healer_runs(created_at DESC);
```

**Fetch previous metrics** (new node, runs in parallel with tests):
```javascript
// Query last 5 runs from Supabase
const resp = await fetch(
  `${SUPABASE_URL}/rest/v1/auto_healer_runs?select=*&order=created_at.desc&limit=5`,
  { headers: { 'apikey': SUPABASE_ANON_KEY, 'Content-Type': 'application/json' } }
);
const history = await resp.json();
return [{ json: { history, latest: history[0] || null } }];
```

**Store results** (replaces static data storage):
```javascript
// Upsert to Supabase
await fetch(`${SUPABASE_URL}/rest/v1/auto_healer_runs`, {
  method: 'POST',
  headers: {
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates'
  },
  body: JSON.stringify({
    run_id: dashboard.run_id,
    overall_score: dashboard.overall_score,
    sector_scores: dashboard.sectors,
    pipeline_health: dashboard.pipelines,
    test_results: testDetails,
    llm_proposals: analysis.proposals,
    execution_analytics: execAnalytics,
    flags: dashboard.flags
  })
});
```

### 3.6 Better Claude Code CLI Integration

**Current CLI** (`ops/auto-healer-cli.py`): Fetches and displays the last report.

**V2.0 CLI output format** (structured for easy consumption):

```
══════════════════════════════════════════════════
 AUTO-HEALER V2.0 REPORT — ah-1710000000000
 2026-03-10T14:30:00Z
══════════════════════════════════════════════════

SYSTEM HEALTH: YELLOW

PIPELINES:
  Standard   HEALTHY   98% success   p50: 3.2s   p95: 8.1s
  Graph      DEGRADED  82% success   p50: 4.1s   p95: 12.3s  [!]
  Quant      HEALTHY   95% success   p50: 5.0s   p95: 9.8s
  Orchestr.  HEALTHY   91% success   p50: 6.2s   p95: 14.1s

SECTORS vs TARGETS:
  Finance    72% / 90%  (gap: 18pp)  citation: 45%  lang: 90%  [!!]
  BTP        38% / 85%  (gap: 47pp)  citation: 20%  lang: 80%  [!!!]
  Juridique  65% / 90%  (gap: 25pp)  citation: 55%  lang: 95%  [!!]
  Industrie  58% / 85%  (gap: 27pp)  citation: 30%  lang: 85%  [!!]

TRENDS (vs last run):
  Overall: 58% → 58% (=)  |  Finance: +2pp  BTP: -1pp  Juri: =  Ind: +3pp

ERROR DISTRIBUTION:
  TIMEOUT: 12  RATE_LIMIT: 5  EMBEDDING: 3  LLM: 2  UNKNOWN: 1

══════════════════════════════════════════════════
 IMPROVEMENT PROPOSALS (ranked by impact/risk)
══════════════════════════════════════════════════

[P1] #1: Improve Standard prompt for BTP sector terminology
  Pipeline: Standard | Node: LLM Generation
  Change: Add BTP domain vocabulary to system prompt
  Expected: +8% on BTP | Confidence: 0.7 | Risk: LOW
  Rollback: Revert system prompt to previous version
  Effort: 5 min

[P2] #2: Increase topK for juridique queries
  Pipeline: Standard | Node: Init & ACL Pre-Filter V3.4
  Change: Set juridique-specific topK to 25 (from 15)
  Expected: +5% on Juridique | Confidence: 0.6 | Risk: LOW
  Rollback: Reset topK to 15
  Effort: 3 min

[P3] #3: Add French BM25 stopwords to improve keyword search
  Pipeline: Standard | Node: BM25 Search Postgres
  Change: Update bm25_search_sectors function with FR stopwords
  Expected: +3% overall | Confidence: 0.5 | Risk: MEDIUM
  Rollback: Restore previous SQL function
  Effort: 15 min

DATA QUALITY ISSUES:
  - BTP sector has only 4,443 docs (lowest). Need more DTU/Eurocode content
  - 30% of finance docs are US-centric, not matching FR sector questions
```

**CLI enhancements**:

```python
# ops/auto-healer-cli.py V2.0 additions

def render_dashboard(report):
    """Render structured dashboard for terminal output."""
    # Color coding based on health
    # Severity indicators: [!] = degraded, [!!] = gap>15pp, [!!!] = gap>30pp
    # Trend arrows: +N, -N, =
    pass

def render_proposals(proposals):
    """Render ranked proposals with risk assessment."""
    for i, p in enumerate(proposals, 1):
        risk_color = {'LOW': 'green', 'MEDIUM': 'yellow', 'HIGH': 'red'}[p['risk']]
        # Format proposal with priority badge, details, rollback
    pass

def apply_proposal(proposal_id, report):
    """Interactively apply a proposal (with confirmation)."""
    # 1. Show exact change
    # 2. Ask for confirmation
    # 3. Apply via n8n API or workflow JSON edit
    # 4. Run quick smoke test
    # 5. Report result
    pass

def show_history(days=7):
    """Show trend chart from Supabase history."""
    # Fetch last N days of auto-healer runs
    # Show accuracy trend line per sector
    pass
```

---

## 4. New Workflow Node Layout

### V2.0 Node List (14 nodes, up from 10)

| Node | Type | Purpose | Position |
|------|------|---------|----------|
| Every 15min | scheduleTrigger | Cron trigger (was 30min) | [200, 400] |
| Manual Trigger Webhook | webhook POST | Manual trigger | [200, 600] |
| Init Config V2 | code | Config, targets, 40 questions, sector vocab | [500, 500] |
| Execution Analytics V2 | code | 50 execs/pipeline, error categorization | [800, 300] |
| Comprehensive Tests | code | 20 questions, 4 pipelines, quality scoring | [800, 500] |
| Fetch Previous Metrics | httpRequest | GET from Supabase (last 5 runs) | [800, 700] |
| Aggregate Metrics | code | Merge analytics + tests + history | [1100, 500] |
| LLM Deep Analysis | httpRequest | Multi-factor analysis, ranked proposals | [1400, 500] |
| Build Dashboard Data | code | Structured metrics for CLI | [1700, 500] |
| Store to Supabase | httpRequest | Persistent storage | [2000, 300] |
| Store to Static Data | code | Fast cache (existing) | [2000, 500] |
| Respond to Trigger | respondToWebhook | Return report | [2000, 700] |
| GET Results Webhook | webhook GET | Serve cached report | [2300, 700] |
| Serve Dashboard + History | code | Return dashboard + trend data | [2600, 700] |

### V2.0 Connections

```
Every 15min ─────────────┐
Manual Trigger Webhook ──┤
                         ↓
                   Init Config V2
                         │
              ┌──────────┼──────────┐
              ↓          ↓          ↓
   Execution      Comprehensive   Fetch Previous
   Analytics V2   Tests           Metrics
              │          │          │
              └──────────┼──────────┘
                         ↓
                  Aggregate Metrics
                         ↓
                  LLM Deep Analysis
                         ↓
                Build Dashboard Data
                         │
              ┌──────────┼──────────┐
              ↓          ↓          ↓
        Store to    Store to    Respond to
        Supabase    Static Data Trigger

GET Results Webhook → Serve Dashboard + History
```

---

## 5. Improvement Tracking Across Runs

### Improvement History Schema

Each auto-healer run stores:
```json
{
  "run_id": "ah-1710000000000",
  "proposals_generated": [
    { "id": 1, "title": "...", "status": "PROPOSED" }
  ],
  "proposals_applied": [
    { "id": 1, "applied_at": "...", "before_score": 58, "after_score": 63, "status": "SUCCESS" }
  ],
  "cumulative_improvement": "+12pp since first run"
}
```

### Cross-Run Comparison

The LLM analysis prompt includes:
```
IMPROVEMENT HISTORY (last 5 runs):
- Run ah-001: Proposed prompt change → Applied → +5pp Finance
- Run ah-002: Proposed topK increase → Applied → +3pp Juridique
- Run ah-003: Proposed retrieval change → SKIPPED (too risky)
- Run ah-004: Proposed prompt change → Applied → REGRESSION -2pp BTP (reverted)
- Run ah-005: (current run)

DO NOT re-propose changes that were already tried and failed.
Prioritize approaches that have historically worked (prompt changes, topK tuning).
```

This gives the LLM historical context to avoid repeating failed changes and build on successful patterns.

---

## 6. Testing All 4 Pipelines

### V2.0 Test Matrix

| Pipeline | Questions | Sectors Tested | Webhook |
|----------|-----------|---------------|---------|
| Standard | 8 (2/sector) | All 4 | `/webhook/rag-multi-index-v3` |
| Graph | 4 (1/sector) | All 4 | `/webhook/ff622742-...` |
| Quant | 4 (finance only) | Finance | `/webhook/3e0f8010-...` |
| Orchestrator | 4 (1/sector) | All 4 | `/webhook/orchestrator-v2` |
| **Total** | **20** | | |

### Pipeline-Specific Scoring

- **Standard**: Full quality scoring (keyword + citation + language + sector relevance)
- **Graph**: Additional scoring for entity mentions and relationship descriptions
- **Quant**: Additional scoring for numerical accuracy (expected number ranges)
- **Orchestrator**: Additional scoring for correct pipeline routing (did it pick the right engine?)

```javascript
// Orchestrator-specific scoring
function scoreOrchestratorRouting(response, expectedEngine) {
  const engine = response.engine || response.selected_engine || '';
  const correctRoute = engine.toLowerCase().includes(expectedEngine.toLowerCase());
  return correctRoute ? 100 : 0;
}
```

---

## 7. Migration Path (V1.0 → V2.0)

### Phase 1: Enhance existing nodes (no breaking changes)
1. Expand `Init Config & Targets` with sector vocabulary and 40 questions
2. Update `Fetch Execution Health` to analyze 50 execs with error categorization
3. Update `Run Smoke Tests (5q)` to test 20 questions with quality scoring
4. Update LLM prompt with multi-factor analysis and ranked proposals

### Phase 2: Add new nodes
5. Add `Fetch Previous Metrics` node (Supabase GET, runs in parallel)
6. Add `Aggregate Metrics` node (merge all data sources)
7. Add `Store to Supabase` node (persistent storage)
8. Create `auto_healer_runs` table in Supabase

### Phase 3: CLI upgrade
9. Update `ops/auto-healer-cli.py` with dashboard rendering
10. Add `--history` flag for trend visualization
11. Add `--apply <proposal_id>` for interactive proposal application

### Phase 4: Schedule optimization
12. Change cron from 30min to 15min
13. Add GET `/webhook/auto-healer-history` endpoint for trend queries

---

## 8. Resource Impact

| Resource | V1.0 | V2.0 | Notes |
|----------|------|------|-------|
| n8n execution time | ~90s | ~180s | More tests, more analysis |
| LLM tokens per run | ~2K input + 1K output | ~5K input + 2K output | More context in prompt |
| Supabase storage | 0 | ~1KB/run = ~50KB/day | Minimal |
| API calls per run | 5 (smoke) + 4 (exec fetch) + 1 (LLM) = 10 | 20 (tests) + 4 (exec) + 1 (LLM) + 2 (Supabase) = 27 | More test queries |
| Pinecone queries | 10 (5 tests x 2 index queries each) | 40 (20 tests x 2 index queries) | Within free tier |
| Cron frequency | Every 30min = 48/day | Every 15min = 96/day | Double the runs |

### Rate Limit Considerations
- LiteLLM free tier models: 60 req/min limit
- 20 test questions at ~3 req each (embed + query + LLM) = 60 requests per run
- At 15min intervals, this is well within limits (4 runs/hour, ~240 total API calls/hour)
- The test questions should be distributed across all 4 n8n Spaces (round-robin) to avoid overloading a single Space

---

## 9. Prerequisites

1. **Create Supabase table**: Run the `auto_healer_runs` migration
2. **Get Supabase credentials into n8n env**: `SUPABASE_URL`, `SUPABASE_ANON_KEY` must be available
3. **Verify all 4 pipeline webhooks are accessible** from the n8n Space running the auto-healer
4. **Deploy auto-healer to a dedicated Space** (S5 or S9 recommended, as per MEMORY.md)
5. **Write expanded test question set** (40 questions covering all pipelines and edge cases)

---

## 10. Success Criteria

| Metric | V1.0 | V2.0 Target |
|--------|------|-------------|
| Test coverage | 5 random questions, 1 pipeline | 20 structured questions, 4 pipelines |
| Error categorization | success/error binary | 8 error categories with distribution |
| Metrics tracked | overall score + per-sector avg | 15+ metrics per pipeline and sector |
| Proposal quality | 1 generic patch | 1-3 ranked proposals with confidence scores |
| Historical context | None (volatile static data) | Last 5 runs persistent in Supabase |
| CLI readability | Raw JSON dump | Formatted dashboard with color coding |
| Trend detection | None | Delta comparison, regression alerts |
| Pipeline coverage | Standard only | All 4 (Standard, Graph, Quant, Orchestrator) |
| Quality dimensions | Keyword match only | 5 dimensions (keyword, citation, language, length, sector relevance) |
