Autonomous self-healing cycle. Run this when a pipeline is broken or accuracy has dropped.

Implements the self-healing RAG pattern from 2026 research: continuous monitoring + intelligent detection + automatic recovery.

Steps:
1. **Detect**: Run `/monitor` equivalent — identify which pipeline(s) are failing
2. **Diagnose**: For each failing pipeline:
   - Check last successful execution (n8n API)
   - Compare current vs expected response structure
   - Match symptoms against DEBUG-PLAYBOOK patterns
   - Check if recent changes (git log --since="1 day") correlate
3. **Classify** severity:
   - P0 (Infrastructure): TCP blocked, OOM, n8n down → fix immediately
   - P1 (Rate-limit): 429, quota exhausted → switch keys/models
   - P2 (Workflow): [object Object], bad SQL → patch workflow
   - P3 (Data): missing vectors, stale cache → re-ingest
   - P4 (Model): hallucinations, wrong routing → prompt tuning
4. **Auto-Fix** (for P0-P2 only, when fix is documented):
   - Apply the documented fix from DEBUG-PLAYBOOK
   - Retest with 3 questions
   - If fixed: document in session log, continue
   - If not fixed: escalate to manual with structured report
5. **Verify**: Run quick-test.py to confirm no regressions
6. **Document**: Add any new fix to DEBUG-PLAYBOOK
7. **Report**: Output what was detected, what was fixed, what needs manual attention
