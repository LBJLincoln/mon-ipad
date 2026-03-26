---
name: cross-repo-audit
description: Audit all 5 repos for consistency, broken links, stale configs, and improvement opportunities
---

Run a full cross-repo audit of the Nomos42 ecosystem.

Arguments: $ARGUMENTS (optional: "quick" for surface check, or repo name for single-repo deep dive)

## Steps

1. **Check all 5 repos exist and are accessible**:
   ```
   mon-ipad — NBA core (6 skills, 6 agents)
   nomos-nba-agent — NBA execution (4 skills, 2 agents)
   nomos-dashboard — Dashboard (2 skills, 1 agent)
   nomos-political-alpha — Political Alpha (2 skills, 2 agents)
   rgwa — RGWA generative AI (5 skills, 5 agents)
   ```

2. **Skill audit** — for each skill in .claude/commands/:
   - Has YAML frontmatter (name + description)?
   - References valid file paths?
   - References valid URLs/APIs?
   - Is it coherent with current architecture?
   - Rate quality 1-5

3. **Agent audit** — for each agent in .claude/agents/:
   - Has proper YAML frontmatter?
   - Tools listed are valid?
   - Model assignment matches delegation rules?
   - No stale references?

4. **Config consistency**:
   - CLAUDE.md in each repo is up-to-date?
   - HF Space URLs match current Nomos42 account structure?
   - Supabase connection strings correct?
   - Environment variables documented?

5. **Cross-repo data flow**:
   - Feature engine parity (mon-ipad/features/engine.py = hf-space/features/engine.py)?
   - Data pipeline: predictions → data server → dashboard API → frontend
   - Telegram bot references correct repos?

6. **Generate report** with issues ranked by severity:
   ```
   ## Cross-Repo Audit — YYYY-MM-DD

   ### Critical (blocks operation)
   - ...

   ### Warning (degrades quality)
   - ...

   ### Info (improvement opportunity)
   - ...

   ### Score: X/5 repos healthy
   ```

## Constraints
- Read-only audit — do not modify files without user confirmation
- Use Agent tool with model: "haiku" for parallel file checks
- Report must be actionable with specific file paths
