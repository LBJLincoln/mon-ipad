"""
Nomos42 Research Radar (R3 Agent)
Tracks research papers, repos, and models relevant to NBA prediction.
Searches ArXiv, GitHub, and HuggingFace every 6 hours.
Sends Telegram alerts for high-value discoveries.
"""

import gradio as gr
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import os
import threading
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = "6582544948"
SEARCH_INTERVAL = 6 * 3600  # 6 hours
KNOWN_AUTHORS = ["Montrucchio", "Silver", "Haugh", "Ruiz"]

ARXIV_QUERIES = [
    "NBA prediction",
    "sports betting machine learning",
    "Brier score calibration",
    "basketball win probability",
]

GITHUB_QUERIES = [
    "NBA prediction",
    "sports betting model",
    "basketball ML",
]

HF_SEARCH_URL = (
    "https://huggingface.co/api/models?"
    "search=basketball+prediction&sort=lastModified&limit=10"
)

HIGHLIGHT_KEYWORDS = ["Brier", "calibration", "ensemble"]

# ---------------------------------------------------------------------------
# State (in-memory)
# ---------------------------------------------------------------------------
papers: list[dict] = []
repos: list[dict] = []
hf_models: list[dict] = []
search_log: list[str] = []
_seen_paper_ids: set[str] = set()
_seen_repo_ids: set[str] = set()
_seen_model_ids: set[str] = set()
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"[{ts}] {msg}"
    with _lock:
        search_log.append(entry)
        # keep last 500 entries
        if len(search_log) > 500:
            del search_log[:len(search_log) - 500]
    print(entry)


def _safe_request(url: str, headers: dict | None = None, timeout: int = 30) -> bytes | None:
    """Perform an HTTP GET, returning bytes or None on failure."""
    try:
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:
        _log(f"HTTP error for {url}: {exc}")
        return None


def _send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN:
        _log("Telegram alert skipped (no token)")
        return
    try:
        payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
        _log(f"Telegram alert sent: {text[:80]}...")
    except Exception as exc:
        _log(f"Telegram send failed: {exc}")


# ---------------------------------------------------------------------------
# ArXiv search
# ---------------------------------------------------------------------------

def _fetch_arxiv(query: str) -> list[dict]:
    """Search ArXiv and return list of paper dicts."""
    encoded = urllib.parse.quote(query)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query=all:{encoded}&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending"
    )
    data = _safe_request(url)
    if data is None:
        return []

    results = []
    try:
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            paper_id_el = entry.find("atom:id", ns)
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            if paper_id_el is None or title_el is None:
                continue

            paper_id = (paper_id_el.text or "").strip()
            title = " ".join((title_el.text or "").split())
            abstract = " ".join((summary_el.text or "").split()) if summary_el is not None else ""
            published = (published_el.text or "")[:10] if published_el is not None else ""

            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            link = paper_id  # ArXiv id URL doubles as link
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("type") == "text/html":
                    link = link_el.get("href", paper_id)
                    break

            results.append({
                "id": paper_id,
                "title": title,
                "authors": ", ".join(authors),
                "date": published,
                "abstract": abstract[:200] + ("..." if len(abstract) > 200 else ""),
                "link": link,
                "query": query,
            })
    except ET.ParseError as exc:
        _log(f"ArXiv XML parse error: {exc}")

    return results


def search_arxiv():
    _log("Starting ArXiv search...")
    new_count = 0
    for query in ARXIV_QUERIES:
        found = _fetch_arxiv(query)
        _log(f"  ArXiv '{query}': {len(found)} results")
        for p in found:
            if p["id"] not in _seen_paper_ids:
                _seen_paper_ids.add(p["id"])
                with _lock:
                    papers.insert(0, p)
                new_count += 1

                # Telegram alerts
                abstract_lower = (p["abstract"] + " " + p["title"]).lower()
                if "brier" in abstract_lower:
                    # Check for score < 0.20
                    import re
                    scores = re.findall(r"0\.1\d{2,}", abstract_lower)
                    if scores:
                        _send_telegram(
                            f"<b>R3 Paper Alert</b>\n"
                            f"Brier &lt; 0.20 mentioned!\n"
                            f"<b>{p['title'][:100]}</b>\n"
                            f"Score(s): {', '.join(scores)}\n"
                            f"{p['link']}"
                        )

                for author in KNOWN_AUTHORS:
                    if author.lower() in p["authors"].lower():
                        _send_telegram(
                            f"<b>R3 Known Author</b>\n"
                            f"{author} published new paper:\n"
                            f"<b>{p['title'][:100]}</b>\n"
                            f"{p['link']}"
                        )
                        break

        # Rate-limit between queries
        time.sleep(3)

    # Trim to last 20
    with _lock:
        if len(papers) > 20:
            del papers[20:]

    _log(f"ArXiv search done. {new_count} new papers.")


# ---------------------------------------------------------------------------
# GitHub search
# ---------------------------------------------------------------------------

def search_github():
    _log("Starting GitHub search...")
    new_count = 0
    for query in GITHUB_QUERIES:
        encoded = urllib.parse.quote(query)
        url = f"https://api.github.com/search/repositories?q={encoded}&sort=updated&per_page=10"
        data = _safe_request(url, headers={"Accept": "application/vnd.github.v3+json"})
        if data is None:
            continue

        try:
            result = json.loads(data)
            items = result.get("items", [])
            _log(f"  GitHub '{query}': {len(items)} results")
            for item in items:
                repo_id = str(item.get("id", ""))
                if repo_id in _seen_repo_ids:
                    continue
                _seen_repo_ids.add(repo_id)

                repo_dict = {
                    "id": repo_id,
                    "name": item.get("full_name", ""),
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language", ""),
                    "updated": (item.get("updated_at", "") or "")[:10],
                    "description": (item.get("description", "") or "")[:200],
                    "url": item.get("html_url", ""),
                    "query": query,
                }
                with _lock:
                    repos.insert(0, repo_dict)
                new_count += 1

                # Alert for high-star repos
                if repo_dict["stars"] > 100:
                    name_desc = (repo_dict["name"] + " " + repo_dict["description"]).lower()
                    if any(kw in name_desc for kw in ["nba", "basketball", "sports betting"]):
                        _send_telegram(
                            f"<b>R3 Repo Alert</b>\n"
                            f"High-star repo found ({repo_dict['stars']} stars):\n"
                            f"<b>{repo_dict['name']}</b>\n"
                            f"{repo_dict['description'][:100]}\n"
                            f"{repo_dict['url']}"
                        )

        except (json.JSONDecodeError, KeyError) as exc:
            _log(f"GitHub parse error: {exc}")

        time.sleep(5)  # respect rate limits

    with _lock:
        if len(repos) > 20:
            del repos[20:]

    _log(f"GitHub search done. {new_count} new repos.")


# ---------------------------------------------------------------------------
# HuggingFace models search
# ---------------------------------------------------------------------------

def search_hf_models():
    _log("Starting HuggingFace models search...")
    data = _safe_request(HF_SEARCH_URL)
    if data is None:
        _log("HF models search failed.")
        return

    new_count = 0
    try:
        items = json.loads(data)
        _log(f"  HF models: {len(items)} results")
        for item in items:
            model_id = item.get("id", "") or item.get("modelId", "")
            if not model_id or model_id in _seen_model_ids:
                continue
            _seen_model_ids.add(model_id)

            model_dict = {
                "id": model_id,
                "author": item.get("author", ""),
                "downloads": item.get("downloads", 0),
                "likes": item.get("likes", 0),
                "last_modified": (item.get("lastModified", "") or "")[:10],
                "pipeline_tag": item.get("pipeline_tag", ""),
                "tags": ", ".join(item.get("tags", [])[:5]),
                "url": f"https://huggingface.co/{model_id}",
            }
            with _lock:
                hf_models.insert(0, model_dict)
            new_count += 1

    except (json.JSONDecodeError, KeyError) as exc:
        _log(f"HF models parse error: {exc}")

    with _lock:
        if len(hf_models) > 20:
            del hf_models[20:]

    _log(f"HF models search done. {new_count} new models.")


# ---------------------------------------------------------------------------
# Full search cycle
# ---------------------------------------------------------------------------

def run_full_search():
    _log("=== Full research scan starting ===")
    search_arxiv()
    search_github()
    search_hf_models()
    _log("=== Full research scan complete ===")


# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

def _background_loop():
    """Run search immediately on start, then every SEARCH_INTERVAL seconds."""
    run_full_search()
    while True:
        time.sleep(SEARCH_INTERVAL)
        try:
            run_full_search()
        except Exception as exc:
            _log(f"Background search error: {exc}")


_bg_thread = threading.Thread(target=_background_loop, daemon=True)
_bg_thread.start()


# ---------------------------------------------------------------------------
# Gradio data formatters
# ---------------------------------------------------------------------------

def _highlight(text: str) -> str:
    """Bold highlight keywords in text for display."""
    for kw in HIGHLIGHT_KEYWORDS:
        if kw.lower() in text.lower():
            text = text.replace(kw, f"**{kw}**").replace(kw.lower(), f"**{kw.lower()}**")
    return text


def get_papers_table():
    with _lock:
        snapshot = list(papers)
    if not snapshot:
        return "No papers found yet. First search may take a minute..."

    rows = []
    for p in snapshot:
        title = _highlight(p["title"])
        abstract = _highlight(p["abstract"])
        rows.append(f"### {title}\n"
                     f"**Authors:** {p['authors'][:80]}  \n"
                     f"**Date:** {p['date']} | **Query:** {p['query']}  \n"
                     f"**Abstract:** {abstract}  \n"
                     f"[Link]({p['link']})\n\n---\n")
    return "\n".join(rows)


def get_repos_table():
    with _lock:
        snapshot = list(repos)
    if not snapshot:
        return "No repos found yet. First search may take a minute..."

    rows = []
    for r in snapshot:
        rows.append(
            f"### [{r['name']}]({r['url']})\n"
            f"**Stars:** {r['stars']} | **Language:** {r['language']} | "
            f"**Updated:** {r['updated']}  \n"
            f"**Description:** {r['description']}  \n"
            f"**Query:** {r['query']}\n\n---\n"
        )
    return "\n".join(rows)


def get_hf_table():
    with _lock:
        snapshot = list(hf_models)
    if not snapshot:
        return "No HuggingFace models found yet..."

    rows = []
    for m in snapshot:
        rows.append(
            f"### [{m['id']}]({m['url']})\n"
            f"**Author:** {m['author']} | **Downloads:** {m['downloads']} | "
            f"**Likes:** {m['likes']}  \n"
            f"**Pipeline:** {m['pipeline_tag']} | **Modified:** {m['last_modified']}  \n"
            f"**Tags:** {m['tags']}\n\n---\n"
        )
    return "\n".join(rows)


def get_search_log():
    with _lock:
        snapshot = list(search_log)
    if not snapshot:
        return "No searches performed yet..."
    return "\n".join(reversed(snapshot))


def manual_search():
    """Trigger a manual search from the UI."""
    run_full_search()
    return (
        get_papers_table(),
        get_repos_table(),
        get_hf_table(),
        get_search_log(),
    )


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

theme = gr.themes.Default()

with gr.Blocks(theme=theme, title="Nomos42 Research Radar") as app:
    gr.Markdown(
        "# Nomos42 Research Radar\n"
        "Autonomous research tracker for NBA prediction. "
        "Searches ArXiv, GitHub, and HuggingFace every 6 hours.\n\n"
        "**Alerts:** Telegram notifications for Brier < 0.20 papers, "
        "high-star repos, and known authors."
    )

    with gr.Row():
        search_btn = gr.Button("Force Search Now", variant="primary")
        status_text = gr.Textbox(
            label="Status",
            value=lambda: f"Papers: {len(papers)} | Repos: {len(repos)} | Models: {len(hf_models)} | Log entries: {len(search_log)}",
            interactive=False,
            every=300,
        )

    with gr.Tabs():
        with gr.Tab("Latest Papers"):
            papers_md = gr.Markdown(
                value=get_papers_table,
                every=300,
            )

        with gr.Tab("GitHub Repos"):
            repos_md = gr.Markdown(
                value=get_repos_table,
                every=300,
            )

        with gr.Tab("HF Models"):
            hf_md = gr.Markdown(
                value=get_hf_table,
                every=300,
            )

        with gr.Tab("Research Log"):
            log_md = gr.Markdown(
                value=get_search_log,
                every=300,
            )

        with gr.Tab("Proposals"):
            gr.Markdown("### Research Proposals\nAdd ideas for new features, techniques, or data sources.")
            proposals_box = gr.Textbox(
                label="Proposals",
                lines=20,
                placeholder=(
                    "Enter research proposals here...\n\n"
                    "Example:\n"
                    "- [HIGH] Shot-chart CNN embeddings for player matchup features\n"
                    "- [MED] MC dropout uncertainty for ensemble calibration\n"
                    "- [LOW] Rolling window cross-validation with seasonal decay"
                ),
            )

    search_btn.click(
        fn=manual_search,
        outputs=[papers_md, repos_md, hf_md, log_md],
    )


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
