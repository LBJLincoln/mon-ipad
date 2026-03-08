# Multi-Platform Revenue Setup Guide

> Created: 2026-03-08 | Covers 8 platforms beyond Stripe
> Priority-ordered by ROI for AI/developer products

---

## PRIORITY ORDER (Setup These First)

| Priority | Platform | Est. Setup Time | Why First |
|----------|----------|-----------------|-----------|
| 1 | **Lemon Squeezy** | 10 min | Best fees, MoR, VAT handling, API checkout creation |
| 2 | **Payhip** | 5 min | 0% fee on Pro plan, instant Stripe payouts |
| 3 | **Ko-fi** | 5 min | 0% platform fee on tips, shop for digital products |
| 4 | **Gumroad** (DONE) | -- | Already set up at nomos42.gumroad.com |
| 5 | **GitHub Sponsors** | 15 min | 0% fee, developer audience, recurring revenue |
| 6 | **Buy Me a Coffee** | 5 min | Memberships + one-time, community features |
| 7 | **Product Hunt** | 10 min | Free launch, massive day-1 visibility |
| 8 | **Udemy / Skillshare** | 30+ min | Course format, passive income, huge audience |

**Total setup time: ~80 minutes for all platforms**

---

## 1. Lemon Squeezy (HIGHEST PRIORITY)

### Overview
Merchant of Record (MoR) -- handles all taxes, VAT, compliance for 135+ countries.
You never deal with tax filings for digital sales.

### Sign-up
- **URL:** https://app.lemonsqueezy.com/register
- **Time:** 10 minutes (email + store name + payout info)

### Fees
| Fee Type | Amount |
|----------|--------|
| Platform fee | **5% + $0.50** per transaction |
| International surcharge | +1.5% for non-US transactions |
| Abandoned cart recovery | +5% on recovered sales |
| Affiliate referrals | +3% per affiliate sale |
| Payout fee | Varies by method (PayPal, bank) |

### API Capabilities
| Operation | Supported | Endpoint |
|-----------|-----------|----------|
| List products | YES | `GET /v1/products` |
| Get product | YES | `GET /v1/products/{id}` |
| **Create product** | **NO** | Not available (feature request pending) |
| Update product | NO | Not available |
| List variants | YES | `GET /v1/variants` |
| **Create checkout** | **YES** | `POST /v1/checkouts` |
| List orders | YES | `GET /v1/orders` |
| List customers | YES | `GET /v1/customers` |
| Manage subscriptions | YES | `PATCH /v1/subscriptions/{id}` |
| Webhooks | YES | Real-time event notifications |
| Manage discounts | YES | CRUD operations |
| List files | YES | `GET /v1/files` |

**Authentication:** Bearer token (API key from Settings > API)
**Base URL:** `https://api.lemonsqueezy.com/v1/`
**Rate limit:** 300 requests/minute
**Format:** JSON:API spec

### Key Headers
```
Accept: application/vnd.api+json
Content-Type: application/vnd.api+json
Authorization: Bearer {API_KEY}
```

### Advantages for AI Agent Commerce
- **Checkout API** -- agents can programmatically create unique checkout URLs per customer
- JSON:API format is highly structured and agent-parseable
- Webhook events for real-time order tracking
- Merchant of Record eliminates tax compliance burden
- Test mode for integration development
- Built-in affiliate system (agents as affiliates)

### Setup Steps
1. Register at https://app.lemonsqueezy.com/register
2. Create store (name: "Nomos AI")
3. Add products manually (API cannot create products yet)
4. Go to Settings > API > Create API key
5. Save key to `.env.local` as `LEMONSQUEEZY_API_KEY`
6. Set up webhooks for order notifications

---

## 2. Payhip

### Overview
Simple digital product platform. All features available on free plan.
Only difference between plans is the transaction fee percentage.

### Sign-up
- **URL:** https://payhip.com/auth/register
- **Time:** 5 minutes

### Fees
| Plan | Monthly | Transaction Fee |
|------|---------|-----------------|
| **Free Forever** | $0 | 5% per sale |
| **Plus** | $29/mo | 2% per sale |
| **Pro** | $99/mo | **0% per sale** |

All plans: Stripe/PayPal processing fees (~2.9% + $0.30) still apply.

**Break-even analysis:**
- Plus plan saves money when Payhip fees > $29/mo (i.e., ~$580/mo in sales)
- Pro plan saves money when Payhip fees > $99/mo (i.e., ~$1,980/mo in sales on Free plan)

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| **Create product** | **NO** | Manual only via web UI |
| Manage license keys | YES | Verify, enable, disable, track usage |
| Manage coupons | YES | Create and manage discount codes |
| Webhooks | YES | Sales, refunds, subscriptions |
| Product listing | NO | No read API for products |

**Authentication:** API key from Settings
**Docs:** https://payhip.com/api-reference

### Advantages for AI Agent Commerce
- All features on free plan (no paywall for automation features)
- Instant Stripe payouts (no holding period)
- Built-in digital product delivery (files, courses, memberships)
- Webhook integrations for order automation
- EU VAT handling included
- Limited API, but webhooks cover order flow

### Setup Steps
1. Register at https://payhip.com/auth/register
2. Connect Stripe account
3. Add products manually (4 products = ~15 min)
4. Set up webhooks for order notifications
5. Note API key from Settings

---

## 3. Ko-fi

### Overview
Creator-focused platform. Zero platform fee on donations/tips.
5% on shop sales (waived with Ko-fi Gold at $12/mo).

### Sign-up
- **URL:** https://ko-fi.com/
- **Time:** 5 minutes

### Fees
| Plan | Monthly | Tips Fee | Shop/Membership Fee |
|------|---------|----------|---------------------|
| **Free** | $0 | **0%** | 5% |
| **Ko-fi Gold** | $12/mo | **0%** | **0%** |

Payment processor fees (Stripe/PayPal ~3% + $0.30) always apply.

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| **Create product** | **NO** | Manual only via web UI |
| Read orders | NO | No REST API |
| Webhooks | YES | HTTP POST on payment events |
| Zapier/Make integration | YES | Via third-party connectors |

**No official REST API.** Only webhooks for payment notifications.

### Advantages for AI Agent Commerce
- **0% platform fee on tips** -- best for donation/support model
- Shop supports up to 600 items (free) / 1,500 items (Gold)
- No listing fees, no expiry dates on products
- Community features (followers, posts, gallery)
- Webhook-based automation possible
- Good for "pay what you want" pricing

### Setup Steps
1. Create account at https://ko-fi.com/
2. Connect PayPal or Stripe
3. Enable Shop feature
4. Add digital products manually
5. Set up webhook URL in Settings > API
6. Optional: upgrade to Gold ($12/mo) to eliminate 5% shop fee

---

## 4. Gumroad (ALREADY ACTIVE)

### Overview
Established digital product marketplace. Simple UI but high fees.
Products must be created manually (API is read-only for products).

### Sign-up
- **URL:** https://gumroad.com (Account: nomos42.gumroad.com)
- **Status:** DONE

### Fees
| Fee Type | Amount |
|----------|--------|
| Direct sales | **10% + $0.50** per transaction |
| Discover marketplace sales | **30%** (includes processing) |
| Payment processing | ~2.9% + $0.30 (via Stripe, additional) |

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| List products | YES | `GET /v2/products` |
| Get product | YES | `GET /v2/products/{id}` |
| **Create product** | **NO** | Manual only |
| Update product | YES | `PUT /v2/products/{id}` |
| List sales | YES | `GET /v2/sales` |
| Webhooks (Ping) | YES | `resource_subscription` endpoints |
| Offer codes | YES | CRUD operations |

**Authentication:** Access token from Settings > Advanced > Applications
**Base URL:** `https://api.gumroad.com/v2/`

### Advantages for AI Agent Commerce
- Established marketplace with existing buyer traffic
- JSON-LD compatible for agent product discovery
- Update products via API (price, description)
- Tax handling included (since Jan 2025)
- Simple webhook integration

### Current Products
See `monetisation/GUMROAD-QUICK-SETUP.md` for the 4 products to create manually.

---

## 5. GitHub Sponsors

### Overview
Zero-fee sponsorship platform for open-source developers.
Monthly recurring revenue from developer community.

### Sign-up
- **URL:** https://github.com/sponsors
- **Time:** 15 minutes (requires application review)

### Fees
| Fee Type | Amount |
|----------|--------|
| Platform fee | **0%** |
| Payment processing | GitHub absorbs Stripe fees |
| Payout fee | None (direct to bank) |

**Genuinely 0% total fee** -- GitHub subsidizes everything.

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| List sponsors | YES | GraphQL API |
| List tiers | YES | GraphQL query |
| **Create tiers** | **NO** | Manual via web UI |
| Sponsor events | YES | Webhooks |
| Sponsorable check | YES | GraphQL query |

**Authentication:** GitHub personal access token or OAuth
**API:** GraphQL (https://api.github.com/graphql)

### Advantages for AI Agent Commerce
- **Zero fees** -- every dollar goes to you
- Developer-focused audience (perfect for RAG/AI products)
- Up to 10 one-time tiers + 10 monthly tiers
- Private repo access as tier reward
- GitHub ecosystem integration
- Builds credibility in open-source community

### Suggested Tiers
| Tier | Price | Reward |
|------|-------|--------|
| Coffee | $5/mo | Shoutout in README |
| Supporter | $15/mo | Access to private debug channel |
| Pro | $50/mo | RAG Debug Playbook + monthly office hours |
| Enterprise | $200/mo | Priority support + all products + architecture review |

### Setup Steps
1. Go to https://github.com/sponsors (your GitHub profile)
2. Click "Get sponsored" or "Join the waitlist"
3. Fill application (payout info, description)
4. Wait for approval (usually 1-3 days)
5. Create sponsorship tiers
6. Add sponsor button to repos (`.github/FUNDING.yml`)

### FUNDING.yml
```yaml
github: [your-username]
custom: ["https://nomos42.gumroad.com"]
```

---

## 6. Buy Me a Coffee

### Overview
Creator support platform. 5% fee. Good for memberships
and recurring revenue alongside one-time "extras" purchases.

### Sign-up
- **URL:** https://www.buymeacoffee.com/signup
- **Time:** 5 minutes

### Fees
| Fee Type | Amount |
|----------|--------|
| Platform fee | **5%** |
| Stripe processing | ~2.9% + $0.30 per transaction |
| International surcharge | +1% |
| Payout processing | 0.5% |

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| List supporters | YES | `GET /api/v1/supporters` |
| List members | YES | `GET /api/v1/subscriptions` |
| Get member by ID | YES | `GET /api/v1/subscriptions/{id}` |
| List extras (products) | YES | `GET /api/v1/extras` |
| **Create products** | **NO** | Manual only |
| Webhooks | YES | Payment events |

**Authentication:** Personal access token from Developers page
**Base URL:** `https://developers.buymeacoffee.com/api/v1/`
**Docs:** https://developers.buymeacoffee.com/

### Advantages for AI Agent Commerce
- Memberships for recurring revenue (monthly/annual)
- "Extras" feature for digital product sales
- Built-in email updates to supporters
- Community building features
- Simple embed widgets for any website
- Good name recognition with non-developer audience

### Setup Steps
1. Register at https://www.buymeacoffee.com/signup
2. Set up payment (Stripe)
3. Create "Extras" (digital products) manually
4. Create membership tiers
5. Get API token from Settings > Developers
6. Save to `.env.local` as `BMC_API_KEY`

---

## 7. Product Hunt

### Overview
Not a payment platform -- it is a launch platform for visibility.
Free to use. Can drive massive day-1 traffic to your sales channels.

### Sign-up
- **URL:** https://www.producthunt.com/
- **Time:** 10 minutes

### Fees
| Fee Type | Amount |
|----------|--------|
| Listing | **Free** |
| Launch | **Free** |
| Ship (coming soon pages) | Free |

### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| Submit product | YES | Via web UI or API |
| Get products | YES | GraphQL API |
| Get votes/comments | YES | GraphQL API |
| Webhooks | NO | No webhook support |

**API:** GraphQL (https://api.producthunt.com/v2/api/graphql)
**Authentication:** OAuth2

### Advantages for AI Agent Commerce
- Top 4 products get ~1,500 unique visitors on launch day
- Developer/tech audience (perfect demographic)
- Free credibility signal ("Featured on Product Hunt" badge)
- Can re-launch every 6 months with major updates
- Coming Soon page for pre-launch email collection

### Launch Strategy (for Nomos products)
1. **Pre-launch (1-2 weeks before):**
   - Create Coming Soon page
   - Build email list (target 100+ subscribers)
   - Prepare 5+ screenshots/GIFs
   - Write tagline under 60 characters
   - Line up 5-10 people to upvote early

2. **Launch day:**
   - Post at 12:01 AM PST (maximize 24h window)
   - Tagline: "79+ battle-tested fixes for RAG pipelines in production"
   - First comment: founder story + what problem it solves
   - Respond to every comment within 1 hour
   - Share on Twitter, LinkedIn, Reddit simultaneously

3. **Post-launch:**
   - Follow up with commenters
   - Write "lessons learned" post
   - Update product with feedback

### Best Product to Launch First
**RAG Debug Playbook** -- most universal appeal, clear value prop, $47 price point is impulse-buy territory for developers.

---

## 8. Udemy / Skillshare

### Overview
Course platforms with massive existing audiences.
Passive income after initial content creation effort.

### Udemy

#### Sign-up
- **URL:** https://www.udemy.com/teaching/
- **Time:** 30 minutes (profile + first course outline)

#### Fees / Revenue Share
| Sale Source | Your Share |
|-------------|-----------|
| Your coupon/referral link | **97%** |
| Udemy organic (no coupon) | **37%** |
| Udemy Business subscription | **17.5%** (drops to 15% Jan 2026) |

No upfront fees. Minimum payout threshold: $25.

#### API Capabilities
| Operation | Supported | Notes |
|-----------|-----------|-------|
| **Create course** | **NO** | Manual upload via web UI |
| Course analytics | YES | Instructor API |
| Revenue reports | YES | Instructor API |
| Student management | Partial | Via dashboard |

#### Course Ideas for Nomos
1. **"RAG Debugging Masterclass"** (from Debug Playbook content) -- $49.99
2. **"Build a Multi-Pipeline RAG System with n8n"** -- $99.99
3. **"AI Agent Architecture: From Zero to Production"** -- $79.99

### Skillshare

#### Sign-up
- **URL:** https://www.skillshare.com/teach
- **Time:** 30 minutes

#### Revenue Model
| Source | Your Share |
|--------|-----------|
| Royalty pool (watch time) | ~$0.05-0.10/minute watched |
| Referral commission | **60%** of subscriber's fee |
| Digital shop sales | 90% (10% platform fee) |

Minimum: 75 minutes of watchtime/month to earn anything.

#### Advantages
- Existing audience of millions
- Passive income once course is published
- Referral program is lucrative (60%)
- Good for shorter, focused classes (15-60 min)

### Setup Steps (Udemy)
1. Go to https://www.udemy.com/teaching/
2. Create instructor profile
3. Plan course outline (minimum 30 min of content)
4. Record content (screen recordings work great for dev tools)
5. Upload and publish
6. Promote with instructor coupon (97% revenue)

---

## Fee Comparison Summary

| Platform | Platform Fee | Processing Fee | Total on $47 sale | You Keep |
|----------|-------------|----------------|-------------------|----------|
| **GitHub Sponsors** | 0% | 0% | $0 | **$47.00** |
| **Ko-fi** (Gold) | 0% | ~3.3% | $1.85 | **$45.15** |
| **Stripe Direct** | 0% | 2.9% + $0.30 | $1.66 | **$45.34** |
| **Ko-fi** (Free) | 5% | ~3.3% | $3.90 | **$43.10** |
| **Buy Me a Coffee** | 5% | ~3.4% | $4.19 | **$42.81** |
| **Payhip** (Free) | 5% | ~3.3% | $3.90 | **$43.10** |
| **Payhip** (Pro $99/mo) | 0% | ~3.3% | $1.85 | **$45.15** |
| **Lemon Squeezy** | 5% + $0.50 | included | $2.85 | **$44.15** |
| **Gumroad** | 10% + $0.50 | ~3.2% | $6.71 | **$40.29** |
| **Udemy** (your coupon) | 3% | included | $1.41 | **$45.59** |
| **Udemy** (organic) | 63% | included | $29.61 | **$17.39** |

---

## ACP (Agentic Commerce Protocol) Compatibility

Which platforms support AI agents making purchases?

| Platform | Agent Can Browse | Agent Can Purchase | Agent Can Track | ACP Score |
|----------|-----------------|-------------------|-----------------|-----------|
| **Stripe** | YES (API) | **YES (API)** | YES (API) | 10/10 |
| **Lemon Squeezy** | YES (API) | **YES (Checkout API)** | YES (Webhooks) | 8/10 |
| **Gumroad** | YES (API) | Partial (links only) | YES (API) | 6/10 |
| **Payhip** | NO | NO | YES (Webhooks) | 3/10 |
| **Ko-fi** | NO | NO | YES (Webhooks) | 2/10 |
| **Buy Me a Coffee** | Partial (API) | NO | YES (API) | 3/10 |
| **GitHub Sponsors** | YES (GraphQL) | NO | YES (GraphQL) | 4/10 |
| **Product Hunt** | YES (GraphQL) | N/A | N/A | N/A |
| **Udemy** | NO | NO | NO | 0/10 |

**For AI agent commerce, prioritize: Stripe > Lemon Squeezy > Gumroad**

---

## Environment Variables to Add

After setting up accounts, add these to `.env.local`:

```bash
# Lemon Squeezy
LEMONSQUEEZY_API_KEY=your_api_key_here
LEMONSQUEEZY_STORE_ID=your_store_id

# Payhip
PAYHIP_API_KEY=your_api_key_here

# Ko-fi (webhook only)
KOFI_WEBHOOK_TOKEN=your_webhook_verification_token

# Buy Me a Coffee
BMC_API_KEY=your_personal_access_token

# GitHub Sponsors (use existing GH token)
# GITHUB_TOKEN already in .env.local

# Gumroad (already configured)
# GUMROAD_ACCESS_TOKEN already in .env.local
```

---

## Quick Reference Links

| Platform | Dashboard | API Docs |
|----------|-----------|----------|
| Lemon Squeezy | https://app.lemonsqueezy.com | https://docs.lemonsqueezy.com/api |
| Payhip | https://payhip.com/dashboard | https://payhip.com/api-reference |
| Ko-fi | https://ko-fi.com/manage | https://help.ko-fi.com/hc/en-us/articles/360004162298 |
| Gumroad | https://gumroad.com/dashboard | https://app.gumroad.com/api |
| Buy Me a Coffee | https://www.buymeacoffee.com/dashboard | https://developers.buymeacoffee.com |
| GitHub Sponsors | https://github.com/sponsors/dashboard | https://docs.github.com/graphql |
| Product Hunt | https://www.producthunt.com/my/dashboard | https://api.producthunt.com/v2/docs |
| Udemy | https://www.udemy.com/instructor/ | https://www.udemy.com/developers/ |
