
import json
import os
import sys
from urllib import request, error
from datetime import datetime
from collections import defaultdict

# Add eval directory to sys.path to import run_eval.py functions
EVAL_DIR = os.path.join(os.path.dirname(__file__), 'eval')
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

from importlib.machinery import SourceFileLoader
run_eval_mod = SourceFileLoader("run_eval", os.path.join(EVAL_DIR, "run-eval.py")).load_module()

call_rag = run_eval_mod.call_rag
extract_answer = run_eval_mod.extract_answer
evaluate_answer = run_eval_mod.evaluate_answer
load_questions = run_eval_mod.load_questions
RAG_ENDPOINTS = run_eval_mod.RAG_ENDPOINTS

def main():
    # Set the N8N_API_KEY for the call_rag function indirectly
    # The webhook endpoints implicitly require the API key if they are protected.
    # The `RAG_ENDPOINTS` are static, but the n8n webhooks they point to are protected.
    # For local execution, the environment variable is expected.
    n8n_api_key = os.environ.get("N8N_API_KEY")
    if not n8n_api_key:
        print("N8N_API_KEY environment variable is not set. Please set it before running this script.")
        sys.exit(1)

    print("Loading questions for 'standard' pipeline from phase-1 dataset...")
    all_questions = load_questions(dataset="phase-1")
    standard_questions = all_questions.get("standard")

    if not standard_questions:
        print("No questions found for the 'standard' pipeline in phase-1 dataset.")
        sys.exit(1)

    # Select the first question
    question_to_test = standard_questions[0]
    question_id = question_to_test["id"]
    question_text = question_to_test["question"]
    expected_answer = question_to_test["expected"]

    print(f"\n--- Testing Single Question for 'standard' pipeline ---")
    print(f"Question ID: {question_id}")
    print(f"Question: {question_text}")
    print(f"Expected Answer: {expected_answer}")

    standard_endpoint = RAG_ENDPOINTS.get("standard")
    if not standard_endpoint:
        print("Standard pipeline endpoint not found.")
        sys.exit(1)

    print(f"Calling RAG endpoint: {standard_endpoint}")
    resp = call_rag(standard_endpoint, question_text, timeout=120)

    if resp["error"]:
        print(f"Error calling RAG endpoint: {resp['error']}")
        evaluation = {"correct": False, "method": "ERROR", "f1": 0.0}
        answer = "N/A"
    else:
        answer = extract_answer(resp["data"])
        evaluation = evaluate_answer(answer, expected_answer)
        print(f"RAG Response (extracted answer): {answer}")
        print(f"Evaluation: {evaluation}")

    if evaluation["correct"]:
        print(f"\nResult: PASSED (1/1)")
    else:
        print(f"\nResult: FAILED (0/1)")

if __name__ == "__main__":
    main()
