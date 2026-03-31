#!/usr/bin/env python3
"""
Agent F0 — STRATEGY DEFINER (Layer 0: User Intake)

Takes a raw user idea and produces a structured strategy brief JSON.
Uses Gemini API for AI analysis with rule-based fallback.

Usage:
    python3 f0_strategy_definer.py --user pierre --idea "AI tool for restaurant menu optimization"
    python3 f0_strategy_definer.py --user pierre --idea "Fitness app for busy parents" --tier builder

Output:
    forge-users/{username}/briefs/strategy-{date}.json
"""

import argparse
import json
import logging
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [F0-STRATEGY] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("f0")

ROOT = Path(__file__).resolve().parent.parent.parent
FORGE_USERS = ROOT / "forge-users"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


# ── Gemini API ──────────────────────────────────────────────

def call_gemini(prompt: str) -> str | None:
    """Call Gemini API. Returns response text or None on failure."""
    if not GOOGLE_API_KEY:
        log.warning("GOOGLE_API_KEY not set — using rule-based fallback")
        return None

    url = f"{GEMINI_URL}?key={GOOGLE_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }).encode()

    req = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log.error(f"Gemini API error: {e}")
    except Exception as e:
        log.error(f"Unexpected Gemini error: {e}")
    return None


def extract_json_from_text(text: str) -> dict | None:
    """Extract JSON object from Gemini response text that may contain markdown fences."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    patterns = [
        r"```json\s*\n(.*?)\n\s*```",
        r"```\s*\n(.*?)\n\s*```",
        r"\{.*\}",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.DOTALL)
        if match:
            try:
                candidate = match.group(1) if match.lastindex else match.group(0)
                return json.loads(candidate)
            except (json.JSONDecodeError, IndexError):
                continue
    return None


# ── AI-Powered Strategy Brief ──────────────────────────────

STRATEGY_PROMPT = """You are an elite business strategist combining McKinsey, Y Combinator, and a16z methodologies.

Analyze this business idea and produce a structured strategy brief as a JSON object.

IDEA: {idea}

Return ONLY a valid JSON object with these exact keys:

{{
    "product_type": "one of: SaaS, API, marketplace, tool, content, service",
    "product_name": "short catchy product name suggestion",
    "one_liner": "1-sentence pitch (max 15 words)",
    "target_user": {{
        "demographics": "age, gender, location, income level",
        "psychographics": "motivations, frustrations, aspirations",
        "paying_capacity": "low ($0-20/mo), mid ($20-100/mo), or high ($100+/mo)"
    }},
    "pain_statement": "1 sentence describing the core pain this solves",
    "pain_intensity": 7,
    "pricing_model": "one of: subscription, freemium, one-time, usage-based",
    "pricing_range": {{
        "low": 9,
        "mid": 29,
        "high": 79,
        "currency": "USD",
        "period": "monthly"
    }},
    "market_size": {{
        "tam": "Total addressable market estimate with reasoning",
        "sam": "Serviceable addressable market",
        "som": "Serviceable obtainable market (realistic year 1)"
    }},
    "competitive_landscape": [
        {{
            "name": "Competitor 1",
            "strength": "what they do well",
            "weakness": "gap we can exploit",
            "pricing": "their price point"
        }}
    ],
    "unique_value_prop": "1-2 sentences on why THIS solution wins vs alternatives",
    "mvp_scope": {{
        "core_feature": "the ONE thing the MVP must do",
        "nice_to_have": ["feature 2", "feature 3"],
        "out_of_scope_v1": ["feature to defer"]
    }},
    "go_to_market": {{
        "primary_channel": "best acquisition channel",
        "secondary_channels": ["channel 2", "channel 3"],
        "launch_strategy": "1-sentence launch plan"
    }},
    "risk_factors": ["risk 1", "risk 2", "risk 3"],
    "confidence_score": 72
}}

Important:
- competitive_landscape must have 3-5 real competitors (research actual companies)
- pain_intensity is 1-10 (10 = unbearable)
- confidence_score is 0-100 (your confidence this idea can generate revenue in <90 days)
- pricing_range values are numbers (not strings)
- Be specific and actionable, not generic
"""


def generate_brief_ai(idea: str) -> dict | None:
    """Generate strategy brief using Gemini AI."""
    prompt = STRATEGY_PROMPT.format(idea=idea)
    response = call_gemini(prompt)
    if not response:
        return None

    brief = extract_json_from_text(response)
    if not brief:
        log.warning("Failed to parse Gemini JSON response")
        return None

    # Validate required keys
    required = ["product_type", "pain_statement", "pricing_model", "unique_value_prop", "mvp_scope"]
    missing = [k for k in required if k not in brief]
    if missing:
        log.warning(f"Gemini response missing keys: {missing}")
        return None

    return brief


# ── Rule-Based Fallback ─────────────────────────────────────

PRODUCT_TYPE_KEYWORDS = {
    "SaaS": ["saas", "dashboard", "platform", "subscription", "software", "app", "tool online"],
    "API": ["api", "endpoint", "integration", "webhook", "backend service"],
    "marketplace": ["marketplace", "buy and sell", "connect buyers", "two-sided", "matching"],
    "tool": ["tool", "utility", "calculator", "analyzer", "checker", "generator", "converter"],
    "content": ["content", "course", "ebook", "newsletter", "blog", "media", "video"],
    "service": ["service", "consulting", "freelance", "agency", "coaching", "managed"],
}

PRICING_MODEL_MAP = {
    "SaaS": "subscription",
    "API": "usage-based",
    "marketplace": "freemium",
    "tool": "freemium",
    "content": "one-time",
    "service": "subscription",
}

PRICING_RANGE_MAP = {
    "SaaS": {"low": 9, "mid": 29, "high": 79},
    "API": {"low": 0, "mid": 19, "high": 99},
    "marketplace": {"low": 0, "mid": 5, "high": 15},
    "tool": {"low": 0, "mid": 9, "high": 29},
    "content": {"low": 9, "mid": 29, "high": 99},
    "service": {"low": 49, "mid": 149, "high": 499},
}


def detect_product_type(idea: str) -> str:
    """Detect product type from idea text using keyword matching."""
    idea_lower = idea.lower()
    scores = {}
    for ptype, keywords in PRODUCT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in idea_lower)
        if score > 0:
            scores[ptype] = score
    if scores:
        return max(scores, key=scores.get)
    return "SaaS"


def detect_industry(idea: str) -> str:
    """Detect industry from idea text."""
    idea_lower = idea.lower()
    industries = {
        "food & restaurant": ["restaurant", "food", "menu", "recipe", "kitchen", "chef", "dining", "meal"],
        "fitness & health": ["fitness", "gym", "health", "workout", "exercise", "nutrition", "wellness"],
        "education": ["learn", "course", "education", "student", "teach", "tutor", "school"],
        "finance": ["finance", "money", "invest", "trading", "banking", "payment", "accounting"],
        "e-commerce": ["shop", "store", "sell", "ecommerce", "product", "retail", "buy"],
        "real estate": ["real estate", "property", "rent", "housing", "apartment", "mortgage"],
        "marketing": ["marketing", "seo", "ads", "social media", "content", "brand", "growth"],
        "AI & tech": ["ai", "machine learning", "data", "analytics", "automation", "bot", "algorithm"],
        "entertainment": ["game", "music", "video", "stream", "entertainment", "media"],
        "productivity": ["productivity", "task", "project", "team", "workflow", "schedule", "organize"],
    }
    for industry, keywords in industries.items():
        if any(kw in idea_lower for kw in keywords):
            return industry
    return "technology"


def generate_brief_fallback(idea: str) -> dict:
    """Generate strategy brief using rule-based analysis (no AI required)."""
    product_type = detect_product_type(idea)
    industry = detect_industry(idea)
    pricing_model = PRICING_MODEL_MAP.get(product_type, "subscription")
    pricing_range = PRICING_RANGE_MAP.get(product_type, {"low": 9, "mid": 29, "high": 79})

    # Generate a product name from the idea
    words = idea.split()
    product_name = " ".join(words[:3]).title() if len(words) >= 3 else idea.title()
    if len(product_name) > 30:
        product_name = product_name[:27] + "..."

    brief = {
        "product_type": product_type,
        "product_name": product_name,
        "one_liner": f"A {product_type.lower()} for {industry}",
        "target_user": {
            "demographics": f"Professionals in {industry}, 25-45, urban, mid-income",
            "psychographics": "Time-constrained, wants efficiency, willing to pay for solutions",
            "paying_capacity": "mid ($20-100/mo)",
        },
        "pain_statement": f"People in {industry} waste time and money on manual processes that this {product_type.lower()} can automate.",
        "pain_intensity": 6,
        "pricing_model": pricing_model,
        "pricing_range": {
            **pricing_range,
            "currency": "USD",
            "period": "monthly",
        },
        "market_size": {
            "tam": f"Global {industry} software market (~$10B+)",
            "sam": f"{industry} professionals needing this specific solution (~$500M)",
            "som": f"First 100 paying users in year 1 (~${100 * pricing_range['mid'] * 12:,}/yr)",
        },
        "competitive_landscape": [
            {
                "name": f"Generic {industry} Tool A",
                "strength": "Market leader, large user base",
                "weakness": "Expensive, bloated features",
                "pricing": f"${pricing_range['high'] * 2}/mo",
            },
            {
                "name": f"Startup {industry} Tool B",
                "strength": "Modern UX, good onboarding",
                "weakness": "Limited features, new to market",
                "pricing": f"${pricing_range['mid']}/mo",
            },
            {
                "name": f"Free {industry} Alternative",
                "strength": "Free, open source community",
                "weakness": "No support, manual setup, limited",
                "pricing": "Free",
            },
        ],
        "unique_value_prop": f"AI-powered {product_type.lower()} that solves the core {industry} problem faster and cheaper than existing solutions, with zero setup time.",
        "mvp_scope": {
            "core_feature": f"Core {industry} problem solver — one screen, one action, immediate value",
            "nice_to_have": ["User dashboard", "Analytics/reports", "Team collaboration"],
            "out_of_scope_v1": ["Mobile app", "Enterprise features", "API access"],
        },
        "go_to_market": {
            "primary_channel": "Product Hunt + direct outreach",
            "secondary_channels": ["Reddit communities", "LinkedIn", "SEO/content marketing"],
            "launch_strategy": f"Launch on Product Hunt with a free tier, convert to paid via value demonstration",
        },
        "risk_factors": [
            f"Competitive {industry} market — need strong differentiation",
            "User acquisition cost may exceed initial pricing",
            "Technical complexity of AI features may delay MVP",
        ],
        "confidence_score": 55,
        "_generation_method": "rule-based-fallback",
    }
    return brief


# ── Main Logic ──────────────────────────────────────────────

def generate_strategy_brief(idea: str, user: str, tier: str = "factory") -> dict:
    """Generate a complete strategy brief for the given idea."""
    now = datetime.now(timezone.utc)

    # Try AI first, fall back to rules
    brief = generate_brief_ai(idea)
    generation_method = "gemini-2.0-flash"

    if brief is None:
        log.info("Using rule-based fallback for strategy brief")
        brief = generate_brief_fallback(idea)
        generation_method = "rule-based-fallback"
    else:
        log.info("Strategy brief generated via Gemini AI")

    # Wrap with metadata
    output = {
        "meta": {
            "agent": "F0-strategy-definer",
            "version": "1.0",
            "user": user,
            "tier": tier,
            "generated_at": now.isoformat(),
            "generation_method": generation_method,
            "idea_raw": idea,
        },
        "brief": brief,
        "next_steps": {
            "f1_product_builder": "Run f1_product_builder.py with this brief to create implementation plan",
            "f2_business_strategist": "Run f2_business_strategist.py to deepen market analysis",
            "f3_communication_manager": "Run f3_communication_manager.py to plan launch comms",
        },
    }

    return output


def save_brief(output: dict, user: str) -> Path:
    """Save strategy brief to user's briefs directory. Returns the file path."""
    user_dir = FORGE_USERS / user
    briefs_dir = user_dir / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"strategy-{date_str}.json"
    filepath = briefs_dir / filename

    # Avoid overwriting: append counter if file exists
    counter = 1
    while filepath.exists():
        counter += 1
        filename = f"strategy-{date_str}-{counter}.json"
        filepath = briefs_dir / filename

    filepath.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    log.info(f"Brief saved: {filepath}")
    return filepath


def update_agent_state(user: str, brief_path: Path, idea: str):
    """Update agent-0 state file for swarm coordination."""
    state_dir = FORGE_USERS / user / "data" / "agent-state"
    state_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "agent": "F0-strategy-definer",
        "status": "completed",
        "last_run": datetime.now(timezone.utc).isoformat(),
        "latest_brief": str(brief_path.relative_to(FORGE_USERS / user)),
        "idea": idea,
        "awaiting": ["F1-product-builder", "F2-business-strategist", "F3-communication-manager"],
    }

    state_file = state_dir / "agent-0-state.json"
    state_file.write_text(json.dumps(state, indent=2))
    log.info(f"Agent state updated: {state_file}")


def run(idea: str, user: str, tier: str = "factory") -> dict:
    """Main entry point. Returns the strategy brief dict and saves to disk."""
    log.info(f"Generating strategy brief for user={user} tier={tier}")
    log.info(f"Idea: {idea}")

    # Validate user directory exists (or create it)
    user_dir = FORGE_USERS / user
    if not user_dir.exists():
        log.info(f"Creating user directory: {user_dir}")
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "briefs").mkdir(exist_ok=True)
        (user_dir / "products").mkdir(exist_ok=True)
        (user_dir / "data" / "agent-state").mkdir(parents=True, exist_ok=True)

    output = generate_strategy_brief(idea, user, tier)
    brief_path = save_brief(output, user)
    update_agent_state(user, brief_path, idea)

    return output


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="F0 Strategy Definer — Transforms raw ideas into structured strategy briefs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 f0_strategy_definer.py --user pierre --idea "AI tool for restaurant menu optimization"
  python3 f0_strategy_definer.py --user sarah --idea "Fitness app for busy parents" --tier builder
  python3 f0_strategy_definer.py --user demo --idea "Newsletter for indie hackers" --tier free
        """,
    )
    parser.add_argument("--user", required=True, help="Username (forge-users/{user}/)")
    parser.add_argument("--idea", required=True, help="Raw business idea as text")
    parser.add_argument("--tier", default="factory", choices=["free", "builder", "factory"],
                        help="User tier (default: factory)")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")

    args = parser.parse_args()
    output = run(idea=args.idea, user=args.user, tier=args.tier)

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        brief = output["brief"]
        print(f"\n{'=' * 60}")
        print(f"  STRATEGY BRIEF — {brief.get('product_name', 'Untitled')}")
        print(f"{'=' * 60}")
        print(f"  Type:    {brief.get('product_type', '?')}")
        print(f"  Pitch:   {brief.get('one_liner', '?')}")
        print(f"  Pain:    {brief.get('pain_statement', '?')}")
        print(f"  Model:   {brief.get('pricing_model', '?')}")
        pr = brief.get("pricing_range", {})
        print(f"  Price:   ${pr.get('low', '?')}-${pr.get('high', '?')}/{pr.get('period', 'mo')}")
        print(f"  UVP:     {brief.get('unique_value_prop', '?')}")
        mvp = brief.get("mvp_scope", {})
        print(f"  MVP:     {mvp.get('core_feature', '?')}")
        print(f"  Score:   {brief.get('confidence_score', '?')}/100")
        print(f"  Method:  {output['meta'].get('generation_method', '?')}")
        comps = brief.get("competitive_landscape", [])
        if comps:
            print(f"\n  Competitors ({len(comps)}):")
            for c in comps:
                print(f"    - {c.get('name', '?')}: {c.get('weakness', '?')}")
        print(f"\n  Saved: forge-users/{args.user}/briefs/")
        print(f"  Next:  python3 f1_product_builder.py --user {args.user} --brief briefs/strategy-{datetime.now().strftime('%Y-%m-%d')}.json")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
