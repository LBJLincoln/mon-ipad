#!/usr/bin/env python3
"""
Agent F1 — PRODUCT BUILDER (Layer 1: Strategic Structure)

Reads a strategy brief from F0 and creates a product implementation plan.
Generates directory structure, BUILD-PLAN.md, README.md, and CLAUDE.md.

Usage:
    python3 f1_product_builder.py --user pierre --brief briefs/strategy-2026-03-31.json
    python3 f1_product_builder.py --user pierre --brief briefs/strategy-2026-03-31.json --deploy hf-space

Output:
    forge-users/{username}/products/{product_name}/
        BUILD-PLAN.md
        README.md
        CLAUDE.md
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
    format="%(asctime)s [F1-BUILDER] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("f1")

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
    """Extract JSON object from Gemini response text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
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


# ── Tech Stack Recommendation ──────────────────────────────

TECH_STACKS = {
    "SaaS": {
        "frontend": "Next.js 14 (App Router, TypeScript, Tailwind CSS)",
        "backend": "Next.js API Routes or Python FastAPI",
        "database": "Supabase (PostgreSQL)",
        "auth": "Supabase Auth",
        "hosting": "Vercel (frontend) + HF Space (backend)",
        "payments": "Stripe",
        "analytics": "Vercel Analytics + PostHog",
    },
    "API": {
        "frontend": "Documentation site (Mintlify or Docusaurus)",
        "backend": "Python FastAPI + uvicorn",
        "database": "Supabase (PostgreSQL)",
        "auth": "API keys + rate limiting",
        "hosting": "HF Space (Gradio wrapper) or Vercel Serverless",
        "payments": "Stripe usage-based billing",
        "analytics": "Custom logging + Supabase",
    },
    "marketplace": {
        "frontend": "Next.js 14 (App Router, TypeScript, Tailwind CSS)",
        "backend": "Next.js API Routes + Supabase Edge Functions",
        "database": "Supabase (PostgreSQL + Realtime)",
        "auth": "Supabase Auth (social login)",
        "hosting": "Vercel",
        "payments": "Stripe Connect (marketplace splits)",
        "analytics": "Vercel Analytics + PostHog",
    },
    "tool": {
        "frontend": "Single-page app (React or Svelte)",
        "backend": "Python script or HF Space (Gradio)",
        "database": "LocalStorage or Supabase lite",
        "auth": "Optional (Supabase Auth if needed)",
        "hosting": "HF Space (Gradio) or Vercel static",
        "payments": "Stripe (if premium tier)",
        "analytics": "Plausible or PostHog",
    },
    "content": {
        "frontend": "Next.js or Astro (static site)",
        "backend": "Markdown + CMS (or Supabase)",
        "database": "Supabase or flat files",
        "auth": "Supabase Auth (for gated content)",
        "hosting": "Vercel",
        "payments": "Stripe or Gumroad",
        "analytics": "Vercel Analytics",
    },
    "service": {
        "frontend": "Next.js (booking/portal)",
        "backend": "Next.js API Routes + Supabase",
        "database": "Supabase (PostgreSQL)",
        "auth": "Supabase Auth",
        "hosting": "Vercel",
        "payments": "Stripe subscriptions",
        "analytics": "PostHog",
    },
}

DEPLOY_TARGETS = {
    "hf-space": {
        "name": "HuggingFace Space",
        "best_for": "Python backends, Gradio UIs, ML tools",
        "cost": "Free (CPU), $5+/mo (GPU)",
        "setup": "git subtree push to HF repo",
    },
    "vercel": {
        "name": "Vercel",
        "best_for": "Next.js frontends, static sites, serverless",
        "cost": "Free (hobby), $20/mo (pro)",
        "setup": "vercel deploy or git push",
    },
    "vm": {
        "name": "VM (self-hosted)",
        "best_for": "Long-running services, cron jobs, bots",
        "cost": "Existing VM allocation",
        "setup": "systemd service or cron",
    },
}


# ── File Structure Templates ───────────────────────────────

def get_file_structure(product_type: str, product_name: str) -> dict:
    """Generate recommended file structure based on product type."""
    slug = slugify(product_name)

    base = {
        "root": f"forge-users/{{user}}/products/{slug}/",
        "files": {
            "README.md": "Project overview, setup instructions",
            "CLAUDE.md": "Agent instructions for this product",
            "BUILD-PLAN.md": "Implementation plan and iteration log",
            ".env.example": "Environment variable template",
        },
    }

    type_files = {
        "SaaS": {
            "app/page.tsx": "Main landing/app page",
            "app/layout.tsx": "Root layout with providers",
            "app/api/health/route.ts": "Health check endpoint",
            "app/dashboard/page.tsx": "User dashboard",
            "components/ui/": "Shared UI components",
            "lib/supabase.ts": "Supabase client",
            "lib/stripe.ts": "Stripe integration",
            "package.json": "Node dependencies",
            "tailwind.config.ts": "Tailwind configuration",
            "tsconfig.json": "TypeScript configuration",
        },
        "API": {
            "main.py": "FastAPI application entry point",
            "routes/": "API route handlers",
            "models/": "Pydantic data models",
            "services/": "Business logic",
            "requirements.txt": "Python dependencies",
            "Dockerfile": "Container build",
            "docs/": "API documentation",
        },
        "marketplace": {
            "app/page.tsx": "Marketplace landing",
            "app/listings/page.tsx": "Browse listings",
            "app/listing/[id]/page.tsx": "Single listing",
            "app/dashboard/page.tsx": "Seller dashboard",
            "app/api/listings/route.ts": "Listings CRUD",
            "components/": "Shared components",
            "lib/supabase.ts": "Supabase client",
            "package.json": "Node dependencies",
        },
        "tool": {
            "app.py": "Gradio application (main)",
            "core/": "Core tool logic",
            "utils/": "Utility functions",
            "requirements.txt": "Python dependencies",
            "Dockerfile": "Container build (HF Space)",
        },
        "content": {
            "app/page.tsx": "Landing page",
            "app/blog/page.tsx": "Blog index",
            "app/blog/[slug]/page.tsx": "Blog post",
            "content/": "Markdown content files",
            "components/": "UI components",
            "package.json": "Node dependencies",
        },
        "service": {
            "app/page.tsx": "Service landing",
            "app/book/page.tsx": "Booking page",
            "app/portal/page.tsx": "Client portal",
            "app/api/bookings/route.ts": "Booking API",
            "components/": "UI components",
            "lib/supabase.ts": "Supabase client",
            "package.json": "Node dependencies",
        },
    }

    base["files"].update(type_files.get(product_type, type_files["SaaS"]))
    return base


# ── AI-Powered Build Plan ──────────────────────────────────

BUILD_PROMPT = """You are a senior software architect and product builder.

Given this strategy brief, create a detailed product implementation plan.

STRATEGY BRIEF:
{brief_json}

Return ONLY a valid JSON object with these exact keys:

{{
    "tech_stack": {{
        "frontend": "specific framework + version",
        "backend": "specific framework + version",
        "database": "specific database",
        "auth": "auth solution",
        "hosting": "deployment platform",
        "payments": "payment processor",
        "key_libraries": ["lib1", "lib2", "lib3"]
    }},
    "mvp_features": [
        {{
            "name": "Feature name",
            "priority": "P0",
            "description": "What it does",
            "estimated_hours": 4,
            "acceptance_criteria": "How to verify it works"
        }}
    ],
    "iteration_plan": [
        {{
            "step": 1,
            "name": "MVP",
            "goal": "Core functionality working",
            "features": ["feature1", "feature2"],
            "metric": "What to measure",
            "target": "Success threshold",
            "estimated_iterations": 10
        }},
        {{
            "step": 2,
            "name": "Alpha",
            "goal": "+2-3 features, feedback loop",
            "features": ["feature3", "feature4"],
            "metric": "What to measure",
            "target": "Success threshold",
            "estimated_iterations": 15
        }},
        {{
            "step": 3,
            "name": "Beta",
            "goal": "Design, onboarding, analytics",
            "features": ["feature5", "feature6"],
            "metric": "What to measure",
            "target": "Success threshold",
            "estimated_iterations": 20
        }},
        {{
            "step": 4,
            "name": "Pro",
            "goal": "Scale, performance, monetization",
            "features": ["feature7", "feature8"],
            "metric": "What to measure",
            "target": "Success threshold",
            "estimated_iterations": 25
        }}
    ],
    "deployment_target": "hf-space or vercel or vm",
    "estimated_total_iterations": 70,
    "key_risks": ["risk1", "risk2"],
    "first_iteration": {{
        "file_to_create": "filename",
        "what_to_build": "description",
        "how_to_test": "test command or method",
        "success_metric": "what makes this iteration pass"
    }}
}}

Important:
- mvp_features should have 4-8 features with P0 (must have), P1 (should have), P2 (nice to have)
- Each iteration_plan step follows the Karpathy pattern: modify -> test 5 min -> measure -> keep if better
- deployment_target should match the product type (tools -> hf-space, SaaS -> vercel, etc.)
- first_iteration is the very first thing to build and test
- Be specific and actionable
"""


def generate_plan_ai(brief: dict) -> dict | None:
    """Generate build plan using Gemini AI."""
    prompt = BUILD_PROMPT.format(brief_json=json.dumps(brief, indent=2))
    response = call_gemini(prompt)
    if not response:
        return None

    plan = extract_json_from_text(response)
    if not plan:
        log.warning("Failed to parse Gemini JSON response for build plan")
        return None

    required = ["tech_stack", "mvp_features", "iteration_plan", "deployment_target"]
    missing = [k for k in required if k not in plan]
    if missing:
        log.warning(f"Gemini response missing keys: {missing}")
        return None

    return plan


def generate_plan_fallback(brief: dict) -> dict:
    """Generate build plan using rule-based approach."""
    product_type = brief.get("product_type", "SaaS")
    product_name = brief.get("product_name", "Product")
    pain = brief.get("pain_statement", "solve the core problem")
    pricing_model = brief.get("pricing_model", "subscription")
    mvp_scope = brief.get("mvp_scope", {})
    core_feature = mvp_scope.get("core_feature", f"Core {product_type} functionality")
    nice_to_have = mvp_scope.get("nice_to_have", ["Dashboard", "Analytics"])

    tech = TECH_STACKS.get(product_type, TECH_STACKS["SaaS"])
    deploy = "hf-space" if product_type in ("tool", "API") else "vercel"

    # Build feature list
    features = [
        {
            "name": core_feature,
            "priority": "P0",
            "description": f"The core value proposition — {pain}",
            "estimated_hours": 8,
            "acceptance_criteria": "User can complete the primary action end-to-end",
        },
        {
            "name": "User authentication",
            "priority": "P0",
            "description": "Sign up, login, session management",
            "estimated_hours": 3,
            "acceptance_criteria": "User can create account and login",
        },
        {
            "name": "Landing page",
            "priority": "P0",
            "description": "Hero section, value prop, CTA",
            "estimated_hours": 4,
            "acceptance_criteria": "Page loads, CTA links to signup",
        },
    ]

    for i, feat in enumerate(nice_to_have[:3]):
        features.append({
            "name": feat,
            "priority": "P1" if i < 2 else "P2",
            "description": f"Additional feature: {feat}",
            "estimated_hours": 4,
            "acceptance_criteria": f"{feat} is functional and tested",
        })

    if pricing_model in ("subscription", "freemium", "usage-based"):
        features.append({
            "name": "Payment integration",
            "priority": "P1",
            "description": f"Stripe {pricing_model} billing",
            "estimated_hours": 6,
            "acceptance_criteria": "User can subscribe and payment is recorded",
        })

    plan = {
        "tech_stack": {
            **tech,
            "key_libraries": _get_key_libraries(product_type),
        },
        "mvp_features": features,
        "iteration_plan": [
            {
                "step": 1,
                "name": "MVP",
                "goal": f"Core functionality: {core_feature}",
                "features": [core_feature, "Landing page"],
                "metric": "Core action completion rate",
                "target": "1 user can complete the full flow",
                "estimated_iterations": 10,
            },
            {
                "step": 2,
                "name": "Alpha",
                "goal": "Auth + 2 extra features + feedback loop",
                "features": ["User authentication"] + nice_to_have[:2],
                "metric": "User retention after 3 sessions",
                "target": ">50% users return",
                "estimated_iterations": 15,
            },
            {
                "step": 3,
                "name": "Beta",
                "goal": "Design polish, onboarding, analytics",
                "features": ["Onboarding flow", "Analytics dashboard", "Email notifications"],
                "metric": "Time-to-value (seconds from signup to first value)",
                "target": "<120 seconds",
                "estimated_iterations": 20,
            },
            {
                "step": 4,
                "name": "Pro",
                "goal": "Scale, performance, monetization",
                "features": ["Payment integration", "Performance optimization", "SEO"],
                "metric": "Conversion rate (free -> paid)",
                "target": ">5% conversion",
                "estimated_iterations": 25,
            },
        ],
        "deployment_target": deploy,
        "estimated_total_iterations": 70,
        "key_risks": [
            "Feature creep — stick to MVP scope",
            "Premature optimization — ship ugly, iterate fast",
            "No user feedback — get 3 beta testers in week 1",
        ],
        "first_iteration": _get_first_iteration(product_type, core_feature),
    }

    return plan


def _get_key_libraries(product_type: str) -> list:
    """Get key libraries for the product type."""
    libs = {
        "SaaS": ["@supabase/supabase-js", "stripe", "tailwindcss", "shadcn/ui", "zod"],
        "API": ["fastapi", "uvicorn", "pydantic", "httpx", "python-jose"],
        "marketplace": ["@supabase/supabase-js", "stripe", "tailwindcss", "next-auth"],
        "tool": ["gradio", "pandas", "numpy", "plotly"],
        "content": ["next-mdx-remote", "tailwindcss", "gray-matter", "rehype-pretty-code"],
        "service": ["@supabase/supabase-js", "stripe", "react-day-picker", "tailwindcss"],
    }
    return libs.get(product_type, libs["SaaS"])


def _get_first_iteration(product_type: str, core_feature: str) -> dict:
    """Get the first iteration definition based on product type."""
    iters = {
        "SaaS": {
            "file_to_create": "app/page.tsx",
            "what_to_build": f"Landing page with hero section describing: {core_feature}",
            "how_to_test": "npm run dev -> visit localhost:3000 -> verify hero renders",
            "success_metric": "Page loads in <2s with correct content",
        },
        "API": {
            "file_to_create": "main.py",
            "what_to_build": f"FastAPI app with /health endpoint and one core route for: {core_feature}",
            "how_to_test": "uvicorn main:app -> curl localhost:8000/health",
            "success_metric": "Health returns 200, core route returns valid JSON",
        },
        "tool": {
            "file_to_create": "app.py",
            "what_to_build": f"Gradio interface with one input/output for: {core_feature}",
            "how_to_test": "python app.py -> use Gradio UI at localhost:7860",
            "success_metric": "Input accepted, output generated, no errors",
        },
        "marketplace": {
            "file_to_create": "app/page.tsx",
            "what_to_build": f"Marketplace landing with sample listings for: {core_feature}",
            "how_to_test": "npm run dev -> verify listings render",
            "success_metric": "3 sample listings visible, responsive layout",
        },
        "content": {
            "file_to_create": "app/page.tsx",
            "what_to_build": f"Content site landing page for: {core_feature}",
            "how_to_test": "npm run dev -> verify content renders",
            "success_metric": "Content loads, CTA visible, responsive",
        },
        "service": {
            "file_to_create": "app/page.tsx",
            "what_to_build": f"Service landing with booking CTA for: {core_feature}",
            "how_to_test": "npm run dev -> verify CTA works",
            "success_metric": "CTA clickable, form renders",
        },
    }
    return iters.get(product_type, iters["SaaS"])


# ── Directory & File Creation ──────────────────────────────

def slugify(name: str) -> str:
    """Convert product name to URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:50].strip("-")


def create_product_dir(user: str, product_name: str, brief: dict, plan: dict) -> Path:
    """Create the product directory structure with initial files."""
    slug = slugify(product_name)
    product_dir = FORGE_USERS / user / "products" / slug

    # Create directories
    product_dir.mkdir(parents=True, exist_ok=True)
    product_type = brief.get("product_type", "SaaS")
    file_structure = get_file_structure(product_type, product_name)

    for filepath, description in file_structure["files"].items():
        full_path = product_dir / filepath
        if filepath.endswith("/"):
            full_path.mkdir(parents=True, exist_ok=True)
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            # Only create placeholder for directories; actual files handled below
            if not full_path.exists() and not filepath.endswith((".md", ".json", ".example")):
                full_path.write_text(f"# {description}\n# Auto-generated by F1 Product Builder\n")

    log.info(f"Product directory created: {product_dir}")
    return product_dir


def write_readme(product_dir: Path, brief: dict, plan: dict):
    """Generate README.md for the product."""
    product_name = brief.get("product_name", "Product")
    one_liner = brief.get("one_liner", "")
    product_type = brief.get("product_type", "SaaS")
    pain = brief.get("pain_statement", "")
    uvp = brief.get("unique_value_prop", "")
    tech = plan.get("tech_stack", {})
    deploy = plan.get("deployment_target", "vercel")
    features = plan.get("mvp_features", [])

    p0_features = [f for f in features if f.get("priority") == "P0"]

    readme = f"""# {product_name}

> {one_liner}

## Problem

{pain}

## Solution

{uvp}

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | {tech.get('frontend', 'TBD')} |
| Backend | {tech.get('backend', 'TBD')} |
| Database | {tech.get('database', 'TBD')} |
| Auth | {tech.get('auth', 'TBD')} |
| Hosting | {tech.get('hosting', 'TBD')} |
| Payments | {tech.get('payments', 'TBD')} |

## MVP Features (P0)

"""
    for f in p0_features:
        readme += f"- **{f['name']}**: {f.get('description', '')}\n"

    readme += f"""
## Getting Started

```bash
# Clone and setup
cd forge-users/{{user}}/products/{slugify(product_name)}

# Install dependencies
# (depends on tech stack — see BUILD-PLAN.md)

# Run locally
# (see first_iteration in BUILD-PLAN.md)
```

## Deployment

Target: **{DEPLOY_TARGETS.get(deploy, {}).get('name', deploy)}**

{DEPLOY_TARGETS.get(deploy, {}).get('best_for', '')}

## Built with La Forge Factory

This product was created by the Forge Factory AI agent system.
Powered by 7 autonomous agents using the Karpathy autoresearch pattern.
"""

    (product_dir / "README.md").write_text(readme)
    log.info(f"README.md written")


def write_claude_md(product_dir: Path, brief: dict, plan: dict, user: str):
    """Generate CLAUDE.md (agent instructions) for the product."""
    product_name = brief.get("product_name", "Product")
    product_type = brief.get("product_type", "SaaS")
    pain = brief.get("pain_statement", "")
    deploy = plan.get("deployment_target", "vercel")
    iteration_plan = plan.get("iteration_plan", [])
    first_iter = plan.get("first_iteration", {})

    current_step = iteration_plan[0] if iteration_plan else {}

    claude_md = f"""# {product_name} — Agent Instructions

> Product type: {product_type} | Deploy: {deploy} | User: {user}
> Generated by F1 Product Builder

## Mission

{pain}

## Current Phase

**{current_step.get('name', 'MVP')}** — {current_step.get('goal', 'Build core functionality')}

Metric: {current_step.get('metric', 'completion rate')}
Target: {current_step.get('target', 'working end-to-end')}

## Karpathy Pattern (MANDATORY)

Every change follows this loop:
1. **Modify** one file/feature
2. **Test** (max 5 minutes)
3. **Measure** the key metric
4. **Keep if better**, revert if worse
5. **Repeat**

Log each iteration to `data/iterations/`.

## First Iteration

- File: `{first_iter.get('file_to_create', 'app/page.tsx')}`
- Build: {first_iter.get('what_to_build', 'core feature')}
- Test: `{first_iter.get('how_to_test', 'run and verify')}`
- Pass if: {first_iter.get('success_metric', 'no errors')}

## Rules

1. **1 change per iteration** — never modify multiple things at once
2. **Test before commit** — always verify the change works
3. **Log everything** — each iteration gets a JSON entry
4. **Read other agents' state** — check `data/agent-state/` before deciding
5. **Never ship broken code** — revert if metrics regress
6. **User never touches backend** — handle everything autonomously

## Agent Coordination

Read these files before each decision:
- `data/agent-state/agent-2-state.json` — Business insights (pivot if market shifted)
- `data/agent-state/agent-3-state.json` — Comms promises (features must match messaging)

Write your state to:
- `data/agent-state/agent-1-state.json`

## Deploy Target

**{DEPLOY_TARGETS.get(deploy, {}).get('name', deploy)}**
Setup: {DEPLOY_TARGETS.get(deploy, {}).get('setup', 'standard deploy')}
"""

    (product_dir / "CLAUDE.md").write_text(claude_md)
    log.info(f"CLAUDE.md written")


def write_build_plan(product_dir: Path, brief: dict, plan: dict, meta: dict):
    """Generate BUILD-PLAN.md with the full implementation plan."""
    product_name = brief.get("product_name", "Product")
    gen_method = meta.get("generation_method", "unknown")
    iteration_plan = plan.get("iteration_plan", [])
    features = plan.get("mvp_features", [])
    tech = plan.get("tech_stack", {})
    deploy = plan.get("deployment_target", "vercel")
    total_iters = plan.get("estimated_total_iterations", 70)
    risks = plan.get("key_risks", [])
    first_iter = plan.get("first_iteration", {})

    md = f"""# BUILD PLAN — {product_name}

> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
> Method: {gen_method}
> Estimated iterations to production: {total_iters}

## Tech Stack

| Component | Choice |
|-----------|--------|
"""
    for k, v in tech.items():
        if k != "key_libraries":
            md += f"| {k.replace('_', ' ').title()} | {v} |\n"

    libs = tech.get("key_libraries", [])
    if libs:
        md += f"\nKey libraries: {', '.join(libs)}\n"

    md += f"""
## Deployment Target

**{deploy}** — {DEPLOY_TARGETS.get(deploy, {}).get('name', deploy)}
{DEPLOY_TARGETS.get(deploy, {}).get('best_for', '')}

## MVP Features (Prioritized)

| Priority | Feature | Hours | Acceptance Criteria |
|----------|---------|-------|-------------------|
"""
    for f in features:
        md += f"| {f.get('priority', '?')} | {f['name']} | {f.get('estimated_hours', '?')}h | {f.get('acceptance_criteria', '')} |\n"

    md += f"""
## Iteration Plan (Karpathy Pattern)

Each step: modify -> test 5 min -> measure metric -> keep if better -> repeat

"""
    for step in iteration_plan:
        md += f"""### Step {step['step']}: {step['name']}

**Goal:** {step.get('goal', '')}
**Features:** {', '.join(step.get('features', []))}
**Metric:** {step.get('metric', '')}
**Target:** {step.get('target', '')}
**Estimated iterations:** {step.get('estimated_iterations', '?')}

"""

    md += f"""## First Iteration (START HERE)

- **File:** `{first_iter.get('file_to_create', '?')}`
- **Build:** {first_iter.get('what_to_build', '?')}
- **Test:** `{first_iter.get('how_to_test', '?')}`
- **Pass if:** {first_iter.get('success_metric', '?')}

## Risks

"""
    for risk in risks:
        md += f"- {risk}\n"

    md += """
## Iteration Log

| # | Date | File Changed | Metric Before | Metric After | Kept? | Notes |
|---|------|-------------|---------------|-------------|-------|-------|
| 1 | — | — | — | — | — | Not started |

---

*Built with La Forge Factory — Karpathy autoresearch pattern*
"""

    (product_dir / "BUILD-PLAN.md").write_text(md)
    log.info(f"BUILD-PLAN.md written")


def write_env_example(product_dir: Path, brief: dict, plan: dict):
    """Generate .env.example with required environment variables."""
    product_type = brief.get("product_type", "SaaS")
    deploy = plan.get("deployment_target", "vercel")

    lines = [
        "# Environment variables for this product",
        "# Copy to .env.local and fill in values",
        "",
        "# Supabase",
        "NEXT_PUBLIC_SUPABASE_URL=",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY=",
        "SUPABASE_SERVICE_ROLE_KEY=",
        "",
    ]

    if brief.get("pricing_model") in ("subscription", "freemium", "usage-based"):
        lines += [
            "# Stripe",
            "STRIPE_SECRET_KEY=",
            "STRIPE_WEBHOOK_SECRET=",
            "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=",
            "",
        ]

    if product_type == "API":
        lines += [
            "# API",
            "API_SECRET_KEY=",
            "RATE_LIMIT_PER_MIN=60",
            "",
        ]

    lines += [
        "# AI (if needed)",
        "GOOGLE_API_KEY=",
        "",
        "# Deploy",
        f"DEPLOY_TARGET={deploy}",
        "",
    ]

    (product_dir / ".env.example").write_text("\n".join(lines))
    log.info(f".env.example written")


# ── Agent State ────────────────────────────────────────────

def update_agent_state(user: str, product_dir: Path, product_name: str, plan: dict):
    """Update agent-1 state file for swarm coordination."""
    state_dir = FORGE_USERS / user / "data" / "agent-state"
    state_dir.mkdir(parents=True, exist_ok=True)

    iteration_plan = plan.get("iteration_plan", [])
    current_step = iteration_plan[0] if iteration_plan else {}

    state = {
        "agent": "F1-product-builder",
        "status": "plan-created",
        "current_phase": current_step.get("name", "MVP"),
        "current_phase_goal": current_step.get("goal", ""),
        "last_run": datetime.now(timezone.utc).isoformat(),
        "product_name": product_name,
        "product_dir": str(product_dir.relative_to(FORGE_USERS / user)),
        "deployment_target": plan.get("deployment_target", "vercel"),
        "total_iterations_planned": plan.get("estimated_total_iterations", 70),
        "iterations_completed": 0,
        "features_built": [],
        "features_pending": [f["name"] for f in plan.get("mvp_features", [])],
        "blocked_by": [],
        "needs_from_agent_2": "Market validation and user persona",
        "needs_from_agent_3": "Launch messaging and content plan",
    }

    state_file = state_dir / "agent-1-state.json"
    state_file.write_text(json.dumps(state, indent=2))
    log.info(f"Agent state updated: {state_file}")


# ── Main Logic ──────────────────────────────────────────────

def run(user: str, brief_path: str, deploy_override: str | None = None) -> dict:
    """Main entry point. Reads brief, generates plan, creates product directory."""
    # Resolve brief path
    bp = Path(brief_path)
    if not bp.is_absolute():
        bp = FORGE_USERS / user / brief_path

    if not bp.exists():
        log.error(f"Brief not found: {bp}")
        sys.exit(1)

    log.info(f"Reading brief: {bp}")
    brief_data = json.loads(bp.read_text())

    # Extract brief (handle both raw and wrapped formats)
    if "brief" in brief_data:
        brief = brief_data["brief"]
        meta = brief_data.get("meta", {})
    else:
        brief = brief_data
        meta = {}

    product_name = brief.get("product_name", "untitled-product")
    product_type = brief.get("product_type", "SaaS")
    log.info(f"Product: {product_name} ({product_type})")

    # Generate build plan (AI or fallback)
    plan = generate_plan_ai(brief)
    gen_method = "gemini-2.0-flash"
    if plan is None:
        log.info("Using rule-based fallback for build plan")
        plan = generate_plan_fallback(brief)
        gen_method = "rule-based-fallback"
    else:
        log.info("Build plan generated via Gemini AI")

    # Override deploy target if specified
    if deploy_override:
        plan["deployment_target"] = deploy_override

    plan_meta = {"generation_method": gen_method, **meta}

    # Create product directory and files
    product_dir = create_product_dir(user, product_name, brief, plan)
    write_readme(product_dir, brief, plan)
    write_claude_md(product_dir, brief, plan, user)
    write_build_plan(product_dir, brief, plan, plan_meta)
    write_env_example(product_dir, brief, plan)

    # Save plan JSON
    plan_json_path = product_dir / "plan.json"
    plan_output = {
        "meta": {
            "agent": "F1-product-builder",
            "version": "1.0",
            "user": user,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_method": gen_method,
            "brief_source": str(bp),
        },
        "plan": plan,
    }
    plan_json_path.write_text(json.dumps(plan_output, indent=2, ensure_ascii=False))
    log.info(f"Plan JSON saved: {plan_json_path}")

    # Update agent state
    update_agent_state(user, product_dir, product_name, plan)

    return plan_output


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="F1 Product Builder — Transforms strategy briefs into implementation plans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 f1_product_builder.py --user pierre --brief briefs/strategy-2026-03-31.json
  python3 f1_product_builder.py --user pierre --brief briefs/strategy-2026-03-31.json --deploy hf-space
  python3 f1_product_builder.py --user sarah --brief /absolute/path/to/brief.json --json
        """,
    )
    parser.add_argument("--user", required=True, help="Username (forge-users/{user}/)")
    parser.add_argument("--brief", required=True, help="Path to strategy brief JSON (relative to user dir or absolute)")
    parser.add_argument("--deploy", choices=["hf-space", "vercel", "vm"],
                        help="Override deployment target")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")

    args = parser.parse_args()
    output = run(user=args.user, brief_path=args.brief, deploy_override=args.deploy)

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        plan = output["plan"]
        tech = plan.get("tech_stack", {})
        features = plan.get("mvp_features", [])
        iteration_plan = plan.get("iteration_plan", [])
        first_iter = plan.get("first_iteration", {})
        deploy = plan.get("deployment_target", "vercel")

        print(f"\n{'=' * 60}")
        print(f"  PRODUCT BUILD PLAN")
        print(f"{'=' * 60}")
        print(f"  Deploy:   {DEPLOY_TARGETS.get(deploy, {}).get('name', deploy)}")
        print(f"  Frontend: {tech.get('frontend', '?')}")
        print(f"  Backend:  {tech.get('backend', '?')}")
        print(f"  Database: {tech.get('database', '?')}")
        print(f"  Method:   {output['meta'].get('generation_method', '?')}")

        print(f"\n  Features ({len(features)}):")
        for f in features:
            marker = "*" if f.get("priority") == "P0" else " "
            print(f"    [{f.get('priority', '?')}]{marker} {f['name']} (~{f.get('estimated_hours', '?')}h)")

        print(f"\n  Iteration Plan ({plan.get('estimated_total_iterations', '?')} iterations total):")
        for step in iteration_plan:
            print(f"    Step {step['step']}: {step['name']} — {step.get('goal', '')} (~{step.get('estimated_iterations', '?')} iters)")

        print(f"\n  FIRST ITERATION:")
        print(f"    File:  {first_iter.get('file_to_create', '?')}")
        print(f"    Build: {first_iter.get('what_to_build', '?')}")
        print(f"    Test:  {first_iter.get('how_to_test', '?')}")
        print(f"    Pass:  {first_iter.get('success_metric', '?')}")

        print(f"\n  Output: forge-users/{args.user}/products/")
        print(f"  Files:  README.md, CLAUDE.md, BUILD-PLAN.md, plan.json, .env.example")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
