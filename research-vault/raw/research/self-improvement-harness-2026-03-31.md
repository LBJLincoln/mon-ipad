# Research Scan: self-improvement-harness-2026-03-31


## date
2026-03-31


## mission
Self-improvement harness research for LLMs — autonomous evolution, harness engineering, and agent-driven optimization


## major_frameworks

- **AutoHarness: Automatic Code Harness Synthesis for LLM Agents**: Enables smaller LLMs (Gemini-2.5-Flash) to automatically synthesize code harnesses that constrain agent behavior to legal actions. Uses iterative code refinement with environment feedback to prevent i
  - URL: https://arxiv.org/abs/2603.03329
- **SAGE: Multi-Agent Self-Evolution for LLM Reasoning**: Closed-loop framework enabling LLMs to improve autonomously via co-evolution of 4 specialized agents: Challenger (generates hard tasks), Planner (structures reasoning), Solver (produces answers), Crit
  - URL: https://arxiv.org/html/2603.15255
- **EvoAgentX: An Automated Framework for Evolving Agentic Workflows**: Open-source Python framework enabling construction, evaluation, and refinement of LLM-based agents through automated feedback loops. Generates multi-agent workflows from natural language goals, integr
  - URL: https://github.com/EvoAgentX/EvoAgentX
- **Andrej Karpathy's AutoResearch: The Minimal Agent Loop for Autonomous ML Optimization**: Groundbreaking framework for autonomous ML experimentation. AI agent runs in tight loop: modify code → train 5min → measure loss → commit if better → repeat. Ran 700 experiments in 2 days, discovering
  - URL: https://github.com/karpathy/autoresearch
- **Experiential Reflective Learning for Self-Improving LLM Agents**: Enables LLM agents to learn rapidly from task trajectories by reflecting on outcomes and generating reusable heuristics. Heuristics are retrieved and injected into context at test time to guide execut
  - URL: https://arxiv.org/abs/2603.24639
- **Trajectory-Informed Memory Generation for Self-Improving Agent Systems**: Automatically extracts actionable learnings from agent execution trajectories and uses contextual memory retrieval to improve future performance. Bridges experience collection and knowledge reuse.
  - URL: https://arxiv.org/abs/2603.10600
- **MIT CSAIL: Self-Improvement of LLM Agents through Reinforcement Learning at Scale**: DigiRL framework for autonomous RL applied to realistic digital agent tasks (Android emulator control, web automation). EnCompass system searches over LLM decision paths, filtering for best solutions.
  - URL: https://www.csail.mit.edu/news/helping-ai-agents-search-get-best-results-out-large-language-models
- **Stanford CS329A: Self-Improving AI Agents (Course + Research)**: Comprehensive curriculum covering self-improvement techniques: constitutional AI, verifiers, test-time compute scaling, tool augmentation, memory, multimodal reasoning. Covers both single-agent and mu
  - URL: https://cs329a.stanford.edu/
- **Anthropic Claude 2026: Computer Use Agent & Long-Running Autonomous Operations**: Claude Computer Use Agent enables 21.2 average tool calls per task (+116% in 6 months). Long-running operations enable 50-100+ hour autonomous sprints. 90%+ of Claude's own code is now AI-authored. Hi
  - URL: https://www.anthropic.com/research/long-running-Claude

## open_source_repos

- **Awesome-Self-Evolving-Agents Survey**: Comprehensive taxonomy of 50+ self-evolving agent papers (2023-2026), organized by single-agent, multi-agent, and domain-specific approaches. Includes recent 2026 frameworks: Vision-Zero, Parallel-R1,
- **karpathy/autoresearch**: Reference implementation of Karpathy's autonomous ML optimization loop. Single train.py file, agent-driven hyperparameter/architecture evolution. Production-ready, minimal dependencies.
- **EvoAgentX/EvoAgentX**: Framework for constructing, evaluating, refining LLM-based agents. WorkFlowGenerator auto-creates multi-agent workflows. 25+ built-in tools. Self-evolution via task-specific evaluation.
- **Self-Improving Coding Agent (SICA)**: Demonstrates self-improvement in code generation: 17% → 53% on SWE-Bench Verified. Can be adapted for feature engineering code generation.
- **Awesome-Agent-Papers (LJY)**: Up-to-date survey of LLM Agent papers, methodology, applications, challenges. Complementary to EvoAgentX taxonomy.

## techniques_applicable_to_nba_prediction

- **?**: 
- **?**: 
- **?**: 
- **?**: 
- **?**: 
- **?**: 
- **?**: 

## data_sources

- arXiv papers (March 2026)
- GitHub trending repos (>3K stars)
- Stanford CS329A course materials
- MIT CSAIL announcements
- Anthropic research blog
- Conference proceedings (ICLR'26 workshops, EMNLP'25)

## generated_at
2026-03-31T23:59:59Z
