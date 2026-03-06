"""Contextual Retrieval — Anthropic-style context prefix enrichment.
For each chunk: LLM generates 50-100 token context prefix.
Prepend context to chunk text before embedding → -49% retrieval failures.
"""
import os, sys, json, time, logging, glob, requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("contextual-enrichment")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("ENRICHMENT_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
DATA_DIR = os.environ.get("ENRICHMENT_DATA_DIR", "data")
OUTPUT_DIR = os.environ.get("ENRICHMENT_OUTPUT_DIR", "data_enriched")
BATCH_SIZE = int(os.environ.get("ENRICHMENT_BATCH_SIZE", 5))
RATE_LIMIT_DELAY = float(os.environ.get("ENRICHMENT_RATE_DELAY", 3.0))

PROMPT_TEMPLATE = """<document>
{doc_text}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the context, nothing else. Keep it to 1-2 sentences (50-100 tokens)."""

def call_llm(prompt):
    if not OPENROUTER_KEY:
        log.error("OPENROUTER_API_KEY not set")
        return ""
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 150, "temperature": 0.0},
            timeout=30,
        )
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        log.error(f"LLM call failed: {e}")
        return ""

def enrich_file(filepath):
    with open(filepath) as f:
        items = json.load(f)

    if not isinstance(items, list):
        items = [items]

    # Use first item's full text as document context (or concatenate all)
    doc_text = " ".join(
        (it.get("text") or it.get("content") or it.get("chunk_text", ""))[:2000]
        for it in items[:10]
    )[:8000]

    enriched = []
    for i, item in enumerate(items):
        chunk_text = item.get("text") or item.get("content") or item.get("chunk_text", "")
        if not chunk_text:
            enriched.append(item)
            continue

        prompt = PROMPT_TEMPLATE.format(doc_text=doc_text[:4000], chunk_text=chunk_text[:2000])
        context = call_llm(prompt)

        if context:
            item["original_text"] = chunk_text
            item["text"] = f"{context}\n\n{chunk_text}"
            item["contextual_prefix"] = context
            log.info(f"  [{i+1}/{len(items)}] +context ({len(context)} chars)")
        else:
            log.warning(f"  [{i+1}/{len(items)}] no context generated")

        enriched.append(item)

        if (i + 1) % BATCH_SIZE == 0:
            time.sleep(RATE_LIMIT_DELAY)

    return enriched

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(DATA_DIR, "**/*.json"), recursive=True)
    log.info(f"Found {len(files)} files to enrich")

    for filepath in files:
        rel = os.path.relpath(filepath, DATA_DIR)
        out_path = os.path.join(OUTPUT_DIR, rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if os.path.exists(out_path):
            log.info(f"Skip (exists): {rel}")
            continue

        log.info(f"Enriching: {rel}")
        enriched = enrich_file(filepath)

        with open(out_path, "w") as f:
            json.dump(enriched, f, indent=2)
        log.info(f"Saved: {out_path} ({len(enriched)} items)")

if __name__ == "__main__":
    main()
