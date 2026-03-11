# V14 Orchestrator — Simplification Notes

## DISABLE these nodes (set "disabled": true):
- Redis: Fetch Conversation
- Redis: Store Conv V8
- Postgres L2/L3 Memory
- Postgres: Update Context V8
- Store RLHF Data V8
- Context Compression V10.1

## KEEP these nodes (core test pipeline):
1. Webhook IN
2. Input Merger V8
3. Init V8 Security & Analysis
4. LLM 1: Intent Analyzer (LiteLLM smart)
5. Intent Parser V9
6. LLM 2: Task Planner (LiteLLM fast)
7. Execution Engine V10
8. Response Builder V9
9. Output Router + Return Response
10. Error Handler V8

## WHY:
- Focus on eval/testing, not production features
- Redis/memory add failure points during evals
- Can re-enable later when eval scores are solid
