# Department: CREATIVE / RGWA (D8)

## Mission
Generate high-quality AI art through the RGWA pipeline, curate outputs above quality threshold, and publish consistently to build the Nomos42 creative brand.

## Primary Metric
- **Name:** quality_score
- **Current:** 0 (pre-launch)
- **Target:** > 7.0 / 10.0 (average across published pieces)
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| output_per_day | 0 | 5+ |
| publish_rate | 0% | > 60% |
| curation_pass_rate | 0% | > 40% |
| style_diversity_index | 0 | > 0.70 |
| audience_engagement | 0 | measurable baseline |
| generation_time_s | N/A | < 120 |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| style_preset | none | [abstract, photorealistic, impressionist, cyberpunk, minimalist, surreal] | categorical |
| prompt_template | basic | [basic, detailed, emotional, narrative, technical] | categorical |
| model_provider | none | [stable_diffusion, dalle, midjourney_api, local_sdxl] | categorical |
| quality_threshold | 5.0 | [3.0, 9.0] | 0.5 |
| batch_size | 4 | [1, 16] | 1 |
| cfg_scale | 7.0 | [3.0, 15.0] | 0.5 |
| steps | 30 | [15, 80] | 5 |
| negative_prompt_strength | 0.5 | [0.0, 1.0] | 0.1 |
| seed_variation | random | [random, sequential, golden_ratio] | categorical |
| upscale_factor | 1 | [1, 2, 4] | categorical |
| color_palette | none | [warm, cool, monochrome, vibrant, muted, auto] | categorical |

## Experiment Protocol
1. Load current best generation config (style, model, prompts, quality threshold)
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): generate batch with mutated config, auto-score quality
4. Measure quality_score (automated aesthetic scoring) and output count
5. If average quality_score improved -> keep, commit config
6. If not -> revert to previous config
7. Log result to data/departments/creative/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter perturbation with style exploration
- **Selection:** alternate between quality optimization and style diversity
- **Exploration:** try new style_preset every 5th iteration to maintain variety
- **Quality gate:** never publish below quality_threshold (hard gate)
- **A/B testing:** when engagement data available, weight mutations toward higher-engagement styles

## Tools & Paths
- **Loop script:** scripts/departments/creative/creative-loop.sh
- **Output:** data/departments/creative/karpathy-output.json
- **RGWA repo:** rgwa/ (AI Artistic Generation)
- **RGWA bot:** @RGWAbot (Telegram)
- **Gallery:** nomos-dashboard /rgwa route
- **Channel:** @Nomos42 (Telegram, cross-post)

## Success Criteria
- output_per_day >= 5 sustained for 1 week
- quality_score > 7.0/10.0 average across all published pieces
- publish_rate > 60% (pieces passing curation / total generated)
- At least 3 distinct styles represented in weekly output
- Bot responds to generation requests within 120 seconds
- Zero published pieces below quality_threshold

## Dependencies
- **Upstream:** None (D8 is independent creative pipeline)
- **Downstream:** Dashboard displays gallery, Telegram channel receives posts
- **External:** Image generation APIs, Telegram Bot API
- **Compute:** GPU for generation (external APIs or Colab), CPU for curation scoring
