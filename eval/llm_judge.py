#!/usr/bin/env python3
"""
LLM Judge — Semantic evaluation of RAG pipeline answers.

Replaces brittle keyword-contains matching with LLM-based semantic judgment.
Uses LiteLLM S7 (smart model group) for fast, cheap evaluation.

Features:
  - Handles number format differences (11200 vs "11,2 milliards")
  - Semantic equivalence (same meaning, different words)
  - Multilingual matching (FR/EN)
  - Structured scoring: accuracy, completeness, terminology, sources, language
  - Falls back to keyword matching if LLM unavailable

Usage:
  from eval.llm_judge import judge_answer
  result = judge_answer(question, answer, expected_contains, sector, pipeline)
  # result = {"pass": True, "scores": {...}, "reasoning": "..."}
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error

# ── Config ──
LITELLM_URL = os.environ.get("LITELLM_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
LITELLM_MODEL = "smart"

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

JUDGE_PROMPT = """You are an expert evaluator for a RAG (Retrieval-Augmented Generation) system specialized in sector expertise ({sector}).

Evaluate whether the ANSWER correctly addresses the QUESTION, considering the EXPECTED information.

IMPORTANT RULES:
- Number formats are equivalent: "11200" = "11,200" = "11.200" = "11,2 milliards" = "11.2 billion"
- Currency/unit differences are OK if the value is correct
- Partial answers that contain the key information should PASS
- Language mismatch is OK if the content is correct (FR answer to EN question = acceptable)
- An answer that provides MORE detail than expected should PASS
- Empty or irrelevant answers should FAIL

QUESTION: {question}
EXPECTED (key info that should be in the answer): {expected}
ACTUAL ANSWER: {answer}

Respond with EXACTLY this JSON format (no markdown, no extra text):
{{"pass": true/false, "accuracy": 0-100, "completeness": 0-100, "terminology": 0-100, "reasoning": "1-2 sentence explanation"}}"""

JUDGE_PROMPT_NO_EXPECTED = """You are an expert evaluator for a RAG system specialized in sector expertise ({sector}).

Evaluate whether the ANSWER is a substantive, relevant response to the QUESTION.

QUESTION: {question}
ACTUAL ANSWER: {answer}

A PASS means: the answer is relevant, substantive (not empty/generic), and attempts to answer the question.
A FAIL means: the answer is empty, completely off-topic, or just an error message.

Respond with EXACTLY this JSON format (no markdown, no extra text):
{{"pass": true/false, "accuracy": 0-100, "completeness": 0-100, "terminology": 0-100, "reasoning": "1-2 sentence explanation"}}"""


def _llm_call(prompt, timeout=15):
    """Call LiteLLM S7 for judgment."""
    data = json.dumps({
        "model": LITELLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        LITELLM_URL, data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]


def _normalize_number(text):
    """Normalize numbers for comparison: 11200 = 11,200 = 11.200."""
    text = str(text)
    text = re.sub(r'(\d)[,.\s](\d{3})(?!\d)', r'\1\2', text)
    text = re.sub(r'(\d)[,.](\d{1,2})\s*(milliard|billion|mrd|Mrd)',
                  lambda m: str(int(float(f"{m.group(1)}.{m.group(2)}") * 1000)), text)
    text = re.sub(r'(\d)[,.](\d{1,2})\s*(million|mio|Mio)',
                  lambda m: str(int(float(f"{m.group(1)}.{m.group(2)}") * 1)), text)
    return text


def _keyword_fallback(answer, expected):
    """Original keyword matching as fallback."""
    if not expected:
        return len(str(answer)) > 10

    norm_answer = _normalize_number(str(answer).lower().replace('$', '').replace('%', ''))

    if isinstance(expected, list):
        return any(_normalize_number(str(e).lower()) in norm_answer for e in expected if e)

    norm_expected = _normalize_number(str(expected).lower())
    return norm_expected in norm_answer


def judge_answer(question, answer, expected_contains="", sector="finance", pipeline="standard", use_llm=True):
    """Judge an answer using LLM (with keyword fallback).

    Returns:
        dict with keys: pass, accuracy, completeness, terminology, reasoning, judge_method
    """
    # Quick fail: no answer at all
    if not answer or len(str(answer).strip()) < 5:
        return {
            "pass": False,
            "accuracy": 0, "completeness": 0, "terminology": 0,
            "reasoning": "Empty or near-empty answer",
            "judge_method": "empty_check",
        }

    # Try LLM judge first
    if use_llm:
        try:
            if expected_contains and str(expected_contains).strip():
                prompt = JUDGE_PROMPT.format(
                    question=question[:500],
                    answer=str(answer)[:1000],
                    expected=str(expected_contains)[:200],
                    sector=sector,
                )
            else:
                prompt = JUDGE_PROMPT_NO_EXPECTED.format(
                    question=question[:500],
                    answer=str(answer)[:1000],
                    sector=sector,
                )

            raw = _llm_call(prompt, timeout=15)

            # Parse JSON from response (handle markdown wrapping)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)

            result = json.loads(raw)
            return {
                "pass": bool(result.get("pass", False)),
                "accuracy": int(result.get("accuracy", 0)),
                "completeness": int(result.get("completeness", 0)),
                "terminology": int(result.get("terminology", 0)),
                "reasoning": str(result.get("reasoning", ""))[:300],
                "judge_method": "llm",
            }
        except (json.JSONDecodeError, KeyError, urllib.error.URLError,
                urllib.error.HTTPError, TimeoutError, Exception) as e:
            # Fall through to keyword matching
            pass

    # Fallback: enhanced keyword matching
    passed = _keyword_fallback(answer, expected_contains)
    return {
        "pass": passed,
        "accuracy": 80 if passed else 20,
        "completeness": 70 if passed else 10,
        "terminology": 50,
        "reasoning": f"Keyword {'match' if passed else 'mismatch'} (LLM unavailable)",
        "judge_method": "keyword_fallback",
    }


def batch_judge(items, use_llm=True):
    """Judge multiple items. Each item = dict with question, answer, expected_contains, sector, pipeline.

    Returns list of judgment dicts.
    """
    results = []
    for item in items:
        judgment = judge_answer(
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            expected_contains=item.get("expected_contains", ""),
            sector=item.get("sector", "finance"),
            pipeline=item.get("pipeline", "standard"),
            use_llm=use_llm,
        )
        results.append(judgment)
        time.sleep(0.5)  # Rate limit
    return results


if __name__ == "__main__":
    # Self-test with known cases
    tests = [
        {
            "name": "Number format equivalence",
            "question": "Quel est le EBITDA de Credit Agricole en 2023?",
            "answer": "Le EBITDA de Credit Agricole en 2023 est de 11,2 milliards d'euros.",
            "expected": "11200",
            "should_pass": True,
        },
        {
            "name": "Semantic equivalence (different words)",
            "question": "Qu'est-ce que alternative investments?",
            "answer": "Les investissements alternatifs designent les investissements sur des marches non-cotes.",
            "expected": "portfolio",
            "should_pass": True,  # Answer is correct even without keyword
        },
        {
            "name": "Empty answer",
            "question": "What is Boeing revenue?",
            "answer": "",
            "expected": "66608",
            "should_pass": False,
        },
        {
            "name": "Correct answer no expected",
            "question": "Quels sont les risques du BTP?",
            "answer": "Les principaux risques du secteur BTP incluent les chutes de hauteur (30% des deces).",
            "expected": "",
            "should_pass": True,
        },
    ]

    print("=== LLM Judge Self-Test ===\n")
    for t in tests:
        result = judge_answer(t["question"], t["answer"], t["expected"])
        match = result["pass"] == t["should_pass"]
        symbol = "OK" if match else "MISMATCH"
        print(f"  [{symbol}] {t['name']}")
        print(f"       Expected pass={t['should_pass']}, Got pass={result['pass']}")
        print(f"       Method: {result['judge_method']} | Accuracy: {result['accuracy']}")
        print(f"       Reasoning: {result['reasoning']}")
        print()
