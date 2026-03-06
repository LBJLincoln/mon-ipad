"""Build BM25 index from ingested chunk JSON files.
Reads all .json files under data/ directory, tokenizes text, and pickles a BM25Okapi index.
"""
import os, sys, json, pickle, re, glob, logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bm25-build")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    sys.exit("pip install rank-bm25")

DATA_DIR = os.environ.get("BM25_DATA_DIR", "data")
INDEX_PATH = os.environ.get("BM25_INDEX_PATH", "bm25_index.pkl")

def tokenize(text):
    return re.findall(r'\w+', text.lower())

def load_chunks(data_dir):
    chunks = []
    for path in glob.glob(os.path.join(data_dir, "**/*.json"), recursive=True):
        try:
            with open(path) as f:
                items = json.load(f)
            if isinstance(items, list):
                for item in items:
                    text = item.get("text") or item.get("content") or item.get("chunk_text", "")
                    if text:
                        chunks.append({"text": text, "metadata": item.get("metadata", {}), "source": path})
            elif isinstance(items, dict):
                text = items.get("text") or items.get("content", "")
                if text:
                    chunks.append({"text": text, "metadata": items.get("metadata", {}), "source": path})
        except Exception as e:
            log.warning(f"Skip {path}: {e}")
    return chunks

def build():
    log.info(f"Loading chunks from {DATA_DIR}")
    chunks = load_chunks(DATA_DIR)
    log.info(f"Loaded {len(chunks)} chunks")

    if not chunks:
        log.error("No chunks found. Check DATA_DIR.")
        sys.exit(1)

    corpus = [tokenize(c["text"]) for c in chunks]
    log.info("Building BM25Okapi index...")
    bm25 = BM25Okapi(corpus)

    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks, "corpus": corpus}, f)
    log.info(f"Index saved to {INDEX_PATH} ({len(chunks)} docs)")

if __name__ == "__main__":
    build()
