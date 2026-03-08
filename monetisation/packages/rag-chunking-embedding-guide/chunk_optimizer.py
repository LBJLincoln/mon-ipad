#!/usr/bin/env python3
"""
Chunk Size Optimizer — Automated chunk size testing for RAG systems
Part of: RAG Chunking & Embedding Optimization Guide by Nomos AI

Usage:
    python chunk_optimizer.py --documents ./docs/ --eval-questions eval.json --output results.json
"""

import json
import time
import hashlib
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import tiktoken


@dataclass
class ChunkConfig:
    strategy: str
    chunk_size: int
    overlap: int
    model: str = "gpt-4"


@dataclass
class ChunkResult:
    config: dict
    num_chunks: int
    avg_chunk_tokens: float
    min_chunk_tokens: int
    max_chunk_tokens: int
    total_tokens: int
    processing_time_ms: float


# --- Chunking Strategies ---

def chunk_fixed(text: str, chunk_size: int = 512, overlap: int = 50, model: str = "gpt-4") -> list[str]:
    """Fixed-size token-based chunking with configurable overlap."""
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        if chunk_text.strip():
            chunks.append(chunk_text.strip())
        start = end - overlap
    return chunks


def chunk_semantic(text: str, max_tokens: int = 512, min_tokens: int = 50) -> list[str]:
    """Sentence-boundary aware chunking."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sent_tokens = len(sentence.split()) * 1.3
        if current_length + sent_tokens > max_tokens and current_length >= min_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sent_tokens
        else:
            current_chunk.append(sentence)
            current_length += sent_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def chunk_paragraph(text: str, max_tokens: int = 512) -> list[str]:
    """Paragraph-level chunking."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_tokens = len(para.split()) * 1.3
        if current_length + para_tokens > max_tokens and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_length = para_tokens
        else:
            current_chunk.append(para)
            current_length += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


RECURSIVE_SEPARATORS = ["\n\n\n", "\n\n", "\n", ". ", ", ", " ", ""]

def chunk_recursive(text: str, chunk_size: int = 512, separators: Optional[list] = None) -> list[str]:
    """Recursive chunking with separator hierarchy."""
    if separators is None:
        separators = RECURSIVE_SEPARATORS

    if len(text.split()) * 1.3 <= chunk_size:
        return [text] if text.strip() else []

    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current = []
            current_len = 0

            for part in parts:
                part_len = len(part.split()) * 1.3
                if current_len + part_len > chunk_size and current:
                    chunks.append(sep.join(current))
                    current = [part]
                    current_len = part_len
                else:
                    current.append(part)
                    current_len += part_len

            if current:
                chunks.append(sep.join(current))

            final_chunks = []
            for chunk in chunks:
                if len(chunk.split()) * 1.3 > chunk_size:
                    remaining_seps = separators[separators.index(sep) + 1:]
                    final_chunks.extend(chunk_recursive(chunk, chunk_size, remaining_seps))
                elif chunk.strip():
                    final_chunks.append(chunk.strip())

            return final_chunks

    return [text] if text.strip() else []


STRATEGIES = {
    "fixed": chunk_fixed,
    "semantic": chunk_semantic,
    "paragraph": chunk_paragraph,
    "recursive": chunk_recursive,
}


# --- Testing Framework ---

def analyze_chunks(chunks: list[str], model: str = "gpt-4") -> dict:
    """Analyze chunk statistics."""
    enc = tiktoken.encoding_for_model(model)
    token_counts = [len(enc.encode(c)) for c in chunks]

    return {
        "num_chunks": len(chunks),
        "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
        "min_tokens": min(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "total_tokens": sum(token_counts),
        "std_tokens": (sum((t - sum(token_counts)/len(token_counts))**2 for t in token_counts) / len(token_counts)) ** 0.5 if token_counts else 0,
    }


def test_configuration(documents: list[str], config: ChunkConfig) -> ChunkResult:
    """Test a single chunking configuration on all documents."""
    start = time.time()

    all_chunks = []
    strategy_fn = STRATEGIES[config.strategy]

    for doc in documents:
        if config.strategy == "fixed":
            chunks = strategy_fn(doc, config.chunk_size, config.overlap, config.model)
        elif config.strategy in ("semantic", "paragraph"):
            chunks = strategy_fn(doc, config.chunk_size)
        else:
            chunks = strategy_fn(doc, config.chunk_size)
        all_chunks.extend(chunks)

    elapsed_ms = (time.time() - start) * 1000
    stats = analyze_chunks(all_chunks, config.model)

    return ChunkResult(
        config=asdict(config),
        num_chunks=stats["num_chunks"],
        avg_chunk_tokens=round(stats["avg_tokens"], 1),
        min_chunk_tokens=stats["min_tokens"],
        max_chunk_tokens=stats["max_tokens"],
        total_tokens=stats["total_tokens"],
        processing_time_ms=round(elapsed_ms, 2),
    )


def run_sweep(documents: list[str], output_path: str = "chunk_sweep_results.json"):
    """Run a full parameter sweep across strategies and sizes."""
    configs = [
        ChunkConfig("fixed", 256, 25),
        ChunkConfig("fixed", 512, 50),
        ChunkConfig("fixed", 768, 75),
        ChunkConfig("fixed", 1024, 100),
        ChunkConfig("semantic", 256, 0),
        ChunkConfig("semantic", 512, 0),
        ChunkConfig("semantic", 768, 0),
        ChunkConfig("semantic", 1024, 0),
        ChunkConfig("paragraph", 512, 0),
        ChunkConfig("paragraph", 768, 0),
        ChunkConfig("paragraph", 1024, 0),
        ChunkConfig("recursive", 256, 0),
        ChunkConfig("recursive", 512, 0),
        ChunkConfig("recursive", 768, 0),
        ChunkConfig("recursive", 1024, 0),
    ]

    results = []
    for config in configs:
        print(f"Testing: {config.strategy} @ {config.chunk_size} tokens (overlap={config.overlap})...")
        result = test_configuration(documents, config)
        results.append(asdict(result))
        print(f"  → {result.num_chunks} chunks, avg {result.avg_chunk_tokens} tokens, {result.processing_time_ms}ms")

    # Sort by fewest chunks (proxy for most efficient)
    results.sort(key=lambda x: x["num_chunks"])

    output = {
        "sweep_date": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "num_documents": len(documents),
        "total_chars": sum(len(d) for d in documents),
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {output_path}")
    print(f"\nTop 3 configurations by chunk efficiency:")
    for r in results[:3]:
        c = r["config"]
        print(f"  {c['strategy']} @ {c['chunk_size']}t: {r['num_chunks']} chunks, avg {r['avg_chunk_tokens']}t")

    return results


def load_documents(path: str) -> list[str]:
    """Load text documents from a directory or file."""
    p = Path(path)
    documents = []

    if p.is_file():
        documents.append(p.read_text(encoding="utf-8", errors="ignore"))
    elif p.is_dir():
        for ext in ["*.txt", "*.md", "*.html", "*.json"]:
            for f in p.glob(ext):
                documents.append(f.read_text(encoding="utf-8", errors="ignore"))

    return documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chunk Size Optimizer for RAG Systems")
    parser.add_argument("--documents", required=True, help="Path to documents directory or file")
    parser.add_argument("--output", default="chunk_sweep_results.json", help="Output JSON file")
    args = parser.parse_args()

    documents = load_documents(args.documents)
    if not documents:
        print(f"No documents found at {args.documents}")
        exit(1)

    print(f"Loaded {len(documents)} documents ({sum(len(d) for d in documents):,} chars)")
    run_sweep(documents, args.output)
