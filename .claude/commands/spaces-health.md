---
name: spaces-health
description: Check health of all 6 HF evolution islands and report status.
---

Check health of all 6 HF evolution islands and report status.

Arguments: $ARGUMENTS (optional: "brief" for one-line summary, or space name like "S10")

## Steps

1. **Query all 6 spaces** in parallel using curl:
   ```
   S10: https://nomos42-nba-quant.hf.space/api/status
   S11: https://nomos42-nba-quant-2.hf.space/api/status
   S12: https://nomos42-nba-evo-3.hf.space/api/status
   S13: https://nomos42-nba-evo-4.hf.space/api/status
   S14: https://nomos42-nba-evo-5.hf.space/api/status
   S15: https://nomos42-nba-evo-6.hf.space/api/status
   ```

2. **Extract key metrics** from each response:
   - Status (EVOLVING/SAVING/ERROR)
   - Generation number
   - Best Brier score
   - Best model type
   - Best feature count
   - Mutation rate
   - Stagnation counter

3. **Detect issues**:
   - Any space unreachable → ALERT
   - Stagnation > 50 → suggest diversification
   - Best Brier > 0.24 → population may be stuck
   - Feature count > 200 → cap not enforced
   - Generation not advancing → space may be frozen

4. **Report** in table format:
   ```
   | Space | Gen | Brier | Model | Feat | Mut | Status |
   ```

5. **If issues found**, suggest corrective actions:
   - Restart frozen spaces via HfApi
   - Send diversify command to stagnant islands
   - Flag for user attention if critical

## Constraints
- ZERO ML on VM — only curl/API calls
- Do not restart spaces without user confirmation
- Read-only by default unless $ARGUMENTS contains "fix"
