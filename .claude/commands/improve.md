Analyze recent eval results and identify the highest-impact improvement to make this session.

Arguments: $ARGUMENTS (optional: pipeline name to focus on)

Steps:
1. **Read current state**: `directives/PROJECT-STATE.md` for baselines and targets
2. **Identify gaps**: For each pipeline, calculate delta between current accuracy and target:
   - Standard: current vs 85% target
   - Graph: current vs 70% target
   - Quantitative: current vs 85% target
3. **Prioritize**: Use the GOLD/SILVER/BRONZE matrix from `technicals/PROJECT-ROADMAP.md`:
   - GOLD = high cross-pipeline impact + quick win
   - SILVER = high impact + longer effort
   - BRONZE = low impact + quick win
   - BACKLOG = low impact + long effort
4. **Research**: Check `technicals/PROJECT-ROADMAP.md` Section 2 for applicable improvements
5. **Propose**: Output the top 3 improvements with:
   - Expected accuracy gain (pp)
   - Effort estimate
   - Which pipeline(s) benefit
   - Specific implementation steps
6. **Apply the #1 improvement** if it's a quick win (< 30 min)
7. **Measure**: Run quick-test before and after to quantify the improvement
8. **Document**: Update DEBUG-PLAYBOOK if a new pattern was discovered
