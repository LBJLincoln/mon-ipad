# Whop Marketplace Setup Guide

> For listing Nomos AI RAG products on Whop.com

## 1. Create Whop Account

1. Go to [whop.com/sell](https://whop.com/sell)
2. Sign up with email or Google
3. Complete onboarding — choose "Digital Products" as your category
4. Set up your company/storefront name: **Nomos AI**

## 2. Get Your API Key

1. Log in to [dash.whop.com](https://dash.whop.com)
2. Go to **Settings > Developer** (or visit [dash.whop.com/settings/developer](https://dash.whop.com/settings/developer))
3. Create a new **Company API Key**
4. Copy the key (starts with a token string)
5. Add to `.env.local`:
   ```bash
   WHOP_API_KEY=your_api_key_here
   ```

### Required API Permissions

The key needs these scopes:
- `access_pass:create` — create products
- `access_pass:basic:read` — list products
- `plan:create` — create pricing plans
- `plan:basic:read` — list plans
- `company:basic:read` — list companies

## 3. Find Your Company ID

```bash
source .env.local
python3 monetisation/whop-listings.py --companies
```

This will output something like:
```
  ID:      biz_xxxxxxxxxxxx
  Title:   Nomos AI
  Route:   nomos-ai
  URL:     https://whop.com/nomos-ai
```

Add the company ID to `.env.local`:
```bash
WHOP_COMPANY_ID=biz_xxxxxxxxxxxx
```

## 4. Create Products

### Preview first (dry run):
```bash
source .env.local
python3 monetisation/whop-listings.py --create --dry-run
```

### Create all 14 products:
```bash
source .env.local
python3 monetisation/whop-listings.py --create
```

This will:
- Create each product with title, description, headline, and URL route
- Attach a one-time pricing plan (USD) to each product
- Skip products that already exist (matched by title or route)
- Save results to `monetisation/whop-products.json`

### Verify:
```bash
python3 monetisation/whop-listings.py --list
python3 monetisation/whop-listings.py --list-plans
```

## 5. Post-Creation Steps

After products are created:

1. **Upload product images** via the Whop dashboard at [dash.whop.com](https://dash.whop.com)
2. **Attach delivery files** (ZIP packages from `monetisation/packages/`)
3. **Enable Whop Discover** for marketplace visibility (Settings > Discover)
4. **Set up Stripe Connect** for payouts (Settings > Payments)
5. **Copy checkout links** and update the sales page

## 6. Script Reference

```bash
# All commands
python3 monetisation/whop-listings.py --help        # Show help
python3 monetisation/whop-listings.py --catalog      # Show product catalog (offline)
python3 monetisation/whop-listings.py --companies    # List companies
python3 monetisation/whop-listings.py --list         # List products
python3 monetisation/whop-listings.py --list-plans   # List plans
python3 monetisation/whop-listings.py --create       # Create all products
python3 monetisation/whop-listings.py --create --dry-run  # Preview creation
```

## Fees

| Channel | Fee | Net on $197 sale |
|---------|-----|-----------------|
| Direct link | 2.7% + $0.30 | $184.38 (93.6%) |
| Whop Discover | +3% automation | $178.49 (90.6%) |
| Whop Discover (marketplace) | 30% | $137.90 (70.0%) |

## API Reference

- Base URL: `https://api.whop.com/api/v1`
- Auth: `Authorization: Bearer YOUR_API_KEY`
- Docs: [docs.whop.com/developer/api](https://docs.whop.com/developer/api/getting-started)
- Products: `GET/POST /api/v1/products`
- Plans: `GET/POST /api/v1/plans`
- Companies: `GET /api/v1/companies`
