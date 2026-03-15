#!/usr/bin/env python3
"""
Dev.to Article Poster — Automated publishing via API
Usage:
    export DEVTO_API_KEY="your-key-from-dev.to-settings"
    python3 monetisation/devto-poster.py --draft     # Save as draft (default)
    python3 monetisation/devto-poster.py --publish    # Publish immediately
    python3 monetisation/devto-poster.py --list       # List your articles
"""

import os, sys, json, urllib.request

DEVTO_API_KEY = os.environ.get("DEVTO_API_KEY", "")
API_URL = "https://dev.to/api/articles"

ARTICLE = {
    "title": "How I Built a Multi-RAG System That Handles 61K Questions at 95% Accuracy (Free Tier)",
    "tags": ["rag", "ai", "machinelearning", "tutorial"],
    "canonical_url": "https://rag-mega-bundle.vercel.app",
    "series": "Production RAG Engineering",
}

def read_article_body():
    """Read the Dev.to article body from distribution-posts.md."""
    path = os.path.join(os.path.dirname(__file__), "distribution-posts.md")
    with open(path) as f:
        content = f.read()

    # Extract Dev.to section (between ## 4. Dev.to and ## 5.)
    start = content.find("## 4. Dev.to Article")
    if start == -1:
        print("ERROR: Could not find Dev.to section in distribution-posts.md")
        sys.exit(1)

    # Find next section
    end = content.find("\n## 5.", start)
    if end == -1:
        end = content.find("\n## 6.", start)
    if end == -1:
        end = len(content)

    section = content[start:end].strip()

    # Remove the header and metadata lines, get just the body
    body_start = section.find("**Body:**")
    if body_start != -1:
        body = section[body_start + len("**Body:**"):].strip()
    else:
        body = section

    return body


def post_article(publish=False):
    if not DEVTO_API_KEY:
        print("ERROR: Set DEVTO_API_KEY environment variable")
        print("Get your key from: https://dev.to/settings/extensions → DEV Community API Keys")
        sys.exit(1)

    body = read_article_body()

    payload = {
        "article": {
            "title": ARTICLE["title"],
            "body_markdown": body,
            "tags": ARTICLE["tags"],
            "canonical_url": ARTICLE["canonical_url"],
            "series": ARTICLE["series"],
            "published": publish,
        }
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "api-key": DEVTO_API_KEY,
        },
    )

    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        status = "PUBLISHED" if publish else "DRAFT"
        print(f"[{status}] Article created!")
        print(f"  URL: {result.get('url', 'pending')}")
        print(f"  ID: {result.get('id')}")
        print(f"  Title: {result.get('title')}")
        return result
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode()[:500]}")
        sys.exit(1)


def list_articles():
    if not DEVTO_API_KEY:
        print("ERROR: Set DEVTO_API_KEY")
        sys.exit(1)

    req = urllib.request.Request(
        f"{API_URL}/me?per_page=10",
        headers={"api-key": DEVTO_API_KEY},
    )
    resp = urllib.request.urlopen(req)
    articles = json.loads(resp.read().decode())

    for a in articles:
        status = "LIVE" if a.get("published") else "DRAFT"
        print(f"  [{status}] {a['title']}")
        print(f"    URL: {a.get('url', 'N/A')}")
        print(f"    Reactions: {a.get('positive_reactions_count', 0)} | Comments: {a.get('comments_count', 0)}")

    if not articles:
        print("  No articles found.")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_articles()
    elif "--publish" in sys.argv:
        post_article(publish=True)
    else:
        post_article(publish=False)
        print("\nUse --publish to publish immediately (default saves as draft)")
