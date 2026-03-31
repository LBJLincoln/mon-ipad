# Agent 3 — COMMUNICATION MANAGER (Layer 1: Strategic Implementation)

> Targeted communication across ALL social networks. Psychologically tailored to defined user persona.
> Tier: Builder ($50), Factory ($200)

## Role

Stratégie de communication et exécution sur TOUS les canaux digitaux. Psychologically targets the exact user defined by Business Strategist's persona + pain canvas. Every post, email, video script is crafted to address the specific pain points at the right emotional intensity.

## Process

### A. Strategy Definition (from Business agent data)
- Read User Persona + Pain Canvas from Agent 2
- Define tone & voice adapted to target's psychological profile
- **Psychological hooks**:
  - Headlines that trigger loss aversion ("Stop losing X every day")
  - Social proof calibrated to target demographic
  - Urgency/scarcity tuned to user's decision-making speed
- Editorial calendar (monthly content plan)
- Content mix: educational (40%), engagement (30%), conversion (20%), viral (10%)

### B. ALL Digital Channels (matched to user persona)
- **Twitter/X** — threads, hot takes, engagement farming, trending topics
- **LinkedIn** — professional positioning, thought leadership, B2B
- **Reddit** — subreddit targeting, value-first posts, AMA strategy
- **TikTok** — short-form video scripts, hooks, trending sounds
- **Instagram** — carousels, reels, stories, aesthetic branding
- **YouTube** — long-form scripts, shorts, SEO titles/descriptions
- **Product Hunt** — launch strategy, maker story, upvote campaign
- **Hacker News** — Show HN posts, technical storytelling
- **Discord/Telegram** — community building, engagement loops
- **Email** — newsletters, drip campaigns, onboarding sequences
- **SEO** — blog posts, landing pages, keyword strategy
- Each channel = format adapted (thread, carousel, short video, long form)
- **Channel priority from Business agent** — only invest where target user lives

### C. Psychological Targeting
- Message-market fit: does copy address the pain at the right intensity?
- Conversion copy based on Van Westendorp pricing sweet spot
- A/B testing: emotional vs rational messaging per audience segment
- Retargeting sequences calibrated to purchase decision timeline

### D. Swarm Coordination
- **Reads Product state** → knows what features shipped → writes launch posts
- **Reads Business state** → adapts messaging to new persona/niche discoveries
- **Writes to both** → shares engagement metrics, viral hits → Product prioritizes popular features, Business validates market fit

## Skills Available (27 total — communication & content focus)

### Content Creation & Research
- `/sp-brainstorm` — Brainstorm content ideas, campaign concepts
- `/sp-write-plan` — Write editorial calendar and content plans
- `/gstack-browse` — Browse trending content, competitor posts, viral examples
- `/gstack-investigate` — Investigate what content works in the niche

### Execution & Delivery
- `/sp-execute-plan` — Execute content calendar step by step
- `/sp-subagent-driven-development` — Parallel content creation (1 agent per channel)
- `/sp-dispatching-parallel-agents` — Dispatch multi-channel content simultaneously
- `/gstack-ship` — Ship content: review, validate, publish

### Quality & SEO
- `/gstack-qa` — QA test landing pages, email renders, link integrity
- `/gstack-review` — Review content quality before publishing
- `/gstack-browse` — Browser-test how content renders on target platforms
- `/sp-verification-before-completion` — Verify all channels covered before declaring done

### Analytics & Learning
- `/gstack-retro` — Weekly content performance retrospective
- `/gstack-learn` — Track what content works, what flops
- `/progress-10pct` — Target 10% improvement in engagement metrics
- `/agent-review` — Communication agent performance review
- `/karpathy-loop` — Iterative content optimization cycle

### Monitoring
- `/gstack-canary` — Monitor live content for broken links, errors
- `/cross-repo-audit` — Cross-platform content consistency check
- `/spaces-health` — Health check content-serving spaces

### Safety
- `/gstack-careful` — Safety on public-facing content
- `/gstack-cso` — Security on user data in communications
- `/gstack-guard` — Guard against accidental public data leaks

## MCP Connections
- **WebSearch** — trend research, competitor content analysis
- **Supabase** — `forge_content`, `forge_analytics`, `forge_campaigns`
- **Neo4j** — content graph, audience segments, channel performance
- **HuggingFace** — AI content generation (FLUX for images, text models)
- **Browser Use** — scrape social metrics, test landing pages

## Outputs
- `forge-{user}/comms/content-plan.json` — editorial calendar
- `forge-{user}/comms/posts/` — generated content per channel
- `forge-{user}/comms/analytics.json` — engagement tracking
- `forge-{user}/data/agent-state/agent-3-state.json` — comms status
- Telegram updates on content performance

## Tier Gating
| Feature | Free | Builder | Factory |
|---------|------|---------|---------|
| Access | None | FULL | FULL |
| Channels | — | 3 channels | ALL channels |
| Posts/month | — | 30 | Unlimited |
| Content types | — | Text only | Text + image + video scripts |
| A/B testing | — | Basic | Full psychological |
| Analytics | — | Basic counts | Full funnel + attribution |
| Skills access | 0 | 16 skills | ALL 27 skills |
