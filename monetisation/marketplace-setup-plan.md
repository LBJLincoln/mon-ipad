# Marketplace Setup Plan — Step-by-Step

> Generated: 2026-03-08 | Prioritized by ROI and effort

---

## Phase 1 — This Week (March 8-14)

### 1. Lemon Squeezy — Automated Setup via API
**Effort**: 2 hours | **API Key**: in `.env.local`

```bash
# Steps:
# 1. Create store via API
# 2. Create all 14 products matching Stripe catalog
# 3. Generate checkout links
# 4. Add links to sales page
```

**API Endpoints**:
- `POST /v1/stores` — Create store
- `POST /v1/products` — Create product
- `POST /v1/variants` — Set pricing
- `POST /v1/checkouts` — Generate checkout URLs

**Products to create** (mirror Stripe catalog):
| Product | Price | Type |
|---------|-------|------|
| MEGA BUNDLE | $497 | One-time |
| Architecture Blueprint | $197 | One-time |
| n8n Workflows Pack | $197 | One-time |
| Enterprise Site License | $197 | One-time |
| Agentic Commerce Kit | $197 | One-time |
| Engineering Handbook | $147 | One-time |
| Eval Framework | $127 | One-time |
| Ingestion Toolkit | $97 | One-time |
| Dashboard | $97 | One-time |
| Benchmark Toolkit | $67 | One-time |
| Embeddings Engine | $67 | One-time |
| Debug Playbook | $47 | One-time |
| Claude Code Skills | $47 | One-time |
| Agent Context Kit | $27 | One-time |

**Script**: `monetisation/lemon-squeezy-setup.py`

**Benefit**: MoR (Merchant of Record) — handles global tax compliance like Gumroad but at 5% vs 10%.

---

### 2. Whop — Storefront Setup
**Effort**: 1 hour | **Manual setup at whop.com**

**Steps**:
1. Create account at whop.com
2. Create company/storefront "Nomos AI"
3. Add all 14 products as digital downloads
4. Upload ZIP packages from `monetisation/packages/`
5. Set up Stripe Connect for payouts
6. Enable Whop Discover for marketplace visibility
7. Copy checkout links → update sales page

**Key settings**:
- Product type: Digital download (one-time purchase)
- Enable "Whop Discover" for marketplace exposure
- Set up webhook for delivery automation

---

### 3. n8n Marketplaces — List Workflows
**Effort**: 3 hours | **Manual submission**

**Target platforms** (in priority order):
1. **n8nmarket.com** — Submit n8n Workflows Pack ($197)
2. **managen8n.com** — Submit individual workflows
3. **haveworkflow.com** — Submit workflow templates
4. **n8nworkflowtemplates.com** — Submit simplified templates
5. **n8n.io/workflows** — Submit free templates (lead gen → upsell)

**For each platform**:
1. Create account
2. Prepare workflow JSON exports
3. Write descriptions with screenshots
4. Set pricing
5. Include setup documentation

**Products to list**:
- Standard RAG V3.4 workflow
- Graph RAG V3.3 workflow
- Quant RAG V3.1 workflow
- Website Pipeline bundle (3 workflows)
- Full n8n Pack (all workflows + docs)

**Free template strategy**: Submit 1-2 simplified workflows to n8n.io/workflows for free → link to full paid pack.

---

## Phase 2 — Week 2 (March 15-21)

### 4. Product Hunt Launch Preparation
**Effort**: 4-6 weeks prep | **Launch target**: April 15-20

**Week 1 (NOW)**:
- [ ] Create Product Hunt maker account
- [ ] Follow 50+ relevant products/makers
- [ ] Start engaging with community (upvotes, comments)
- [ ] Draft product page copy

**Week 2-3**:
- [ ] Create product page (teaser mode)
- [ ] Design hero image (1270x760px)
- [ ] Create 4-5 gallery images showing dashboard, architecture, results
- [ ] Record 2-min demo video (Nano Banana if ready)
- [ ] Write first comment (maker story + results)

**Week 4-5**:
- [ ] Build launch list (email, Twitter, LinkedIn)
- [ ] Coordinate with 3-5 early supporters
- [ ] Choose launch day (Tuesday-Thursday, best engagement)
- [ ] Prepare launch day social media posts

**Launch day**:
- [ ] Launch at 12:01 AM PT
- [ ] Post first comment immediately
- [ ] Share on all social channels
- [ ] Respond to every comment within 1 hour
- [ ] Post updates throughout the day

**Product Hunt listing**:
- **Name**: Multi-RAG Orchestrator
- **Tagline**: "Open architecture that scores 87.5% on 10K SOTA benchmarks"
- **Topics**: AI, Developer Tools, Open Source, Automation
- **Pricing**: Free (architecture) + Paid (bundles $27-497)

---

### 5. AppSumo Marketplace Submission
**Effort**: 2 hours setup + 1 week review

**Steps**:
1. Go to sell.appsumo.com
2. Submit product application
3. Provide:
   - Product name: "Multi-RAG AI Architecture Bundle"
   - Category: AI / Developer Tools
   - Regular price: $497 (MEGA BUNDLE)
   - AppSumo price: ~$49-79 (lifetime deal)
   - Product description + screenshots
   - Demo video
4. Wait for review (typically 1 week)
5. If approved, prepare for 60-day refund window

**LTD Strategy**:
- List MEGA BUNDLE at $49 as LTD (90% off)
- Volume play: 500 sales × $49 × 70% = ~$17,150
- Use as lead gen for consulting/custom work

---

### 6. Ko-fi Shop Setup
**Effort**: 30 minutes

**Steps**:
1. Create Ko-fi account
2. Subscribe to Ko-fi Gold ($6/mo) for 0% platform fee
3. Set up shop with lower-price items:
   - Agent Context Kit — $27
   - Debug Playbook — $47
   - Claude Code Skills — $47
   - Benchmark Toolkit — $67
   - Embeddings Engine — $67
4. Upload ZIP files
5. Enable PayPal + Stripe as payment methods
6. Share Ko-fi link on social profiles

---

## Phase 3 — Week 3-4 (March 22 — April 7)

### 7. Community Posts (Indie Hackers + HN)
**Effort**: 2 hours writing + ongoing engagement

**Indie Hackers post**:
- Title: "I built a Multi-RAG system that scores 87.5% on SOTA benchmarks — here's the architecture"
- Content: Architecture deep-dive, lessons learned, results
- CTA: Link to sales page for complete bundles
- Post in: #ai, #side-projects, #show-ih

**Hacker News post**:
- Title: "Show HN: Multi-RAG Orchestrator – 87.5% accuracy, n8n-based, fully documented"
- URL: Link to GitHub repo or sales page
- Strategy: Focus on technical merits, be transparent about commercial products
- Timing: Post Tuesday-Thursday, 9-11 AM ET

---

### 8. PromptBase — Extract & List Prompts
**Effort**: 2 hours

**Steps**:
1. Create seller account on promptbase.com
2. Connect Stripe for payouts
3. Extract individual prompts from our products:
   - RAG pipeline prompt templates (5-10 prompts)
   - Claude Code skill prompts (10-15 prompts)
   - Eval framework question templates (5 prompts)
4. Price each at $3.99-$9.99
5. Create bundle option at $29.99
6. Write descriptions + example outputs for each

---

## Phase 4 — April (Courses)

### 9. Udemy Course
**Effort**: 20-40 hours content creation

**Steps**:
1. Convert `monetisation/course-outline.md` into video scripts
2. Record screen-share lectures (OBS or similar)
3. Create slides for theory sections
4. Record 6-8 hours of content minimum
5. Create quizzes and assignments
6. Upload to Udemy instructor dashboard
7. Set price at $99.99 (Udemy will discount to $12-20 in sales)
8. Use instructor coupon link for 97% revenue share

**Course structure** (from course-outline.md):
- Module 1: RAG Architecture Fundamentals
- Module 2: Building with n8n
- Module 3: Multi-Pipeline Design
- Module 4: Evaluation & Benchmarking
- Module 5: Production Deployment
- Module 6: Advanced Techniques (Graph RAG, Quant RAG)

---

### 10. Teachable (Premium Course)
**Effort**: 5 hours setup (reuse Udemy content)

**Steps**:
1. Create Teachable school
2. Choose Basic plan ($39/mo) — 5% tx fee
3. Upload same content as Udemy but at premium pricing ($297-497)
4. Add exclusive bonuses:
   - 1-on-1 consultation call
   - Access to private Discord/community
   - Monthly live Q&A sessions
5. Market as premium alternative to Udemy version

---

## Automation Script Needed

### `monetisation/multi-channel-sync.py`
Auto-create products across platforms with APIs:

```python
# Platforms with APIs for automated product creation:
AUTOMATED_PLATFORMS = {
    'stripe': True,        # DONE
    'lemon_squeezy': True, # API key ready
    'gumroad': True,       # API available
    'whop': True,          # API available
}

# Platforms requiring manual setup:
MANUAL_PLATFORMS = {
    'appsumo': 'sell.appsumo.com',
    'product_hunt': 'producthunt.com/launch',
    'ko_fi': 'ko-fi.com',
    'n8n_marketplaces': ['n8nmarket.com', 'managen8n.com', 'haveworkflow.com'],
    'promptbase': 'promptbase.com/sell',
    'udemy': 'udemy.com/instructor',
    'teachable': 'teachable.com',
}
```

---

## Checklist Summary

### This Week
- [ ] Lemon Squeezy: Create all 14 products via API
- [ ] Whop: Create storefront + list products
- [ ] n8nmarket.com: Submit workflow products
- [ ] managen8n.com: Submit workflow templates
- [ ] Update sales page with multi-platform checkout links

### This Month
- [ ] Product Hunt: Start community engagement
- [ ] AppSumo: Submit product application
- [ ] Ko-fi: Set up Gold shop
- [ ] Indie Hackers: Publish build story
- [ ] Hacker News: Show HN post
- [ ] PromptBase: Extract and list 20+ prompts

### Next Month
- [ ] Udemy: Record and publish course
- [ ] Teachable: Set up premium course
- [ ] Product Hunt: Execute launch

---

## Expected Revenue Distribution (Monthly, at scale)

| Channel | Est. Monthly Sales | Avg Price | Revenue |
|---------|-------------------|-----------|---------|
| Stripe (direct) | 20 | $120 | $2,400 |
| Gumroad Discover | 10 | $80 | $560 |
| Lemon Squeezy | 8 | $120 | $890 |
| Whop | 5 | $100 | $440 |
| AppSumo | 30 (burst) | $49 | $1,029 |
| n8n marketplaces | 5 | $150 | $675 |
| Ko-fi | 10 | $45 | $430 |
| PromptBase | 20 | $5 | $80 |
| Udemy | 50 | $15 | $560 |
| **Total** | | | **~$7,064/mo** |

Note: Product Hunt launch could drive 500-2000 visits → 20-100 sales in launch week alone.
