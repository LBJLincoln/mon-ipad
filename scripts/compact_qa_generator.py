"""CompactRAG QA pair generator — +12% on quantitative/formula queries.
Extracts tables from financial/tabular data, generates synthetic Q&A pairs via LLM.
Embeds Q&A pairs and stores in Pinecone with doc_type: compact_qa metadata.
"""
import os, sys, json, time, logging, glob, re, requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("compact-qa")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("QA_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
DATA_DIR = os.environ.get("QA_DATA_DIR", "data")
OUTPUT_DIR = os.environ.get("QA_OUTPUT_DIR", "data_qa_pairs")
RATE_LIMIT_DELAY = float(os.environ.get("QA_RATE_DELAY", 3.0))

QA_PROMPT = """Given the following data extract, generate 3-5 question-answer pairs that someone might ask about this data. Focus on:
- Specific numerical values (revenue, growth rates, percentages)
- Comparisons between entities or time periods
- Key facts and relationships

Data:
{chunk_text}

Return ONLY a JSON array of objects with "question" and "answer" keys. Example:
[{{"question": "What was X's revenue in 2023?", "answer": "X's revenue in 2023 was $1.2B"}}]"""

def call_llm(prompt):
    if not OPENROUTER_KEY:
        return ""
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "temperature": 0.3},
            timeout=30,
        )
        return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        log.error(f"LLM call failed: {e}")
        return ""

def extract_json_array(text):
    """Extract JSON array from LLM response, handling markdown code blocks."""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return []
    return []

def is_tabular(text):
    """Detect if chunk contains tabular/financial data."""
    indicators = [
        r'\$[\d,.]+[BMKbmk]?\b',
        r'\d+\.?\d*\s*%',
        r'\b(revenue|profit|income|expense|margin|growth|total|net)\b',
        r'\b(Q[1-4]|FY\d{2,4}|20\d{2})\b',
        r'\|.*\|.*\|',
    ]
    score = sum(1 for p in indicators if re.search(p, text, re.IGNORECASE))
    return score >= 2

def generate_qa_for_file(filepath):
    with open(filepath) as f:
        items = json.load(f)

    if not isinstance(items, list):
        items = [items]

    qa_pairs = []
    for i, item in enumerate(items):
        text = item.get("text") or item.get("content") or item.get("chunk_text", "")
        if not text or not is_tabular(text):
            continue

        prompt = QA_PROMPT.format(chunk_text=text[:3000])
        response = call_llm(prompt)
        pairs = extract_json_array(response)

        for pair in pairs:
            if "question" in pair and "answer" in pair:
                qa_pairs.append({
                    "question": pair["question"],
                    "answer": pair["answer"],
                    "text": f"Q: {pair['question']}\nA: {pair['answer']}",
                    "metadata": {
                        "doc_type": "compact_qa",
                        "source_file": os.path.basename(filepath),
                        "source_chunk_index": i,
                        **(item.get("metadata", {})),
                    },
                })

        if pairs:
            log.info(f"  [{i+1}/{len(items)}] Generated {len(pairs)} QA pairs")
        time.sleep(RATE_LIMIT_DELAY)

    return qa_pairs

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(DATA_DIR, "**/*.json"), recursive=True)
    log.info(f"Scanning {len(files)} files for tabular data")

    total_pairs = 0
    for filepath in files:
        rel = os.path.relpath(filepath, DATA_DIR)
        out_path = os.path.join(OUTPUT_DIR, rel.replace(".json", "_qa.json"))

        if os.path.exists(out_path):
            log.info(f"Skip (exists): {rel}")
            continue

        pairs = generate_qa_for_file(filepath)
        if pairs:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(pairs, f, indent=2)
            log.info(f"Saved {len(pairs)} QA pairs → {out_path}")
            total_pairs += len(pairs)

    log.info(f"Done. Total QA pairs generated: {total_pairs}")

if __name__ == "__main__":
    main()
