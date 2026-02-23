#!/usr/bin/env python3
"""Example integration of OpenRouter key rotation in eval scripts.

This demonstrates how to integrate the key rotator into existing
evaluation scripts like quick-test.py, iterative-eval.py, etc.
"""

import requests
from openrouter_key_rotation import get_rotator


def call_openrouter_with_rotation(prompt: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> str:
    """Call OpenRouter API with automatic key rotation.

    Args:
        prompt: The prompt to send to the LLM
        model: OpenRouter model ID (default: Llama 70B)

    Returns:
        Response text from the LLM

    Raises:
        requests.HTTPError: If the API call fails
    """
    rotator = get_rotator()

    # Get the next available key
    api_key = rotator.get_next_key()

    try:
        # Make the API request
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://nomos-ai.com",
                "X-Title": "Nomos RAG Evaluation",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
            timeout=30,
        )

        response.raise_for_status()

        # Record successful usage
        rotator.record_usage(api_key)

        return response.json()["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] OpenRouter API call failed: {e}")
        # Don't record usage on failure
        raise


def example_sequential():
    """Example: Sequential requests (like quick-test.py)."""
    print("\n=== Sequential Request Example ===\n")

    questions = [
        "What is RAG?",
        "Explain vector databases",
        "What is a knowledge graph?",
        "How does semantic search work?",
        "What are embeddings?",
    ]

    rotator = get_rotator()

    for i, question in enumerate(questions, 1):
        print(f"Question {i}/{len(questions)}: {question}")

        try:
            answer = call_openrouter_with_rotation(
                prompt=question,
                model="google/gemma-3-27b-it:free"  # Fast model for demo
            )
            print(f"Answer: {answer[:100]}...\n")

        except Exception as e:
            print(f"Failed: {e}\n")

    # Show final stats
    print("\n=== Final Statistics ===\n")
    rotator.print_status()


def example_parallel():
    """Example: Parallel requests (like run-eval-parallel.py)."""
    import concurrent.futures

    print("\n=== Parallel Request Example ===\n")

    questions = [
        "What is RAG?",
        "Explain vector databases",
        "What is a knowledge graph?",
        "How does semantic search work?",
        "What are embeddings?",
        "What is chunking?",
        "Explain reranking",
        "What is a hybrid search?",
    ]

    rotator = get_rotator()

    def process_question(question: str) -> str:
        """Process a single question (thread-safe)."""
        try:
            return call_openrouter_with_rotation(
                prompt=question,
                model="google/gemma-3-27b-it:free"
            )
        except Exception as e:
            return f"ERROR: {e}"

    # Process in parallel (up to 5 concurrent requests)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_question, questions))

    # Print results
    for question, answer in zip(questions, results):
        print(f"Q: {question}")
        print(f"A: {answer[:100]}...\n")

    # Show final stats
    print("\n=== Final Statistics ===\n")
    rotator.print_status()


def example_integration_pattern():
    """Example: How to integrate into existing eval script."""
    print("\n=== Integration Pattern Example ===\n")

    print("""
To integrate key rotation into an existing eval script:

1. Import the rotator at the top:
   ```python
   from openrouter_key_rotation import get_rotator
   ```

2. Replace hardcoded API key usage:

   BEFORE:
   ```python
   api_key = os.getenv("OPENROUTER_API_KEY")
   response = requests.post(
       url,
       headers={"Authorization": f"Bearer {api_key}"},
       ...
   )
   ```

   AFTER:
   ```python
   rotator = get_rotator()  # Once at script start

   # For each request:
   api_key = rotator.get_next_key()
   response = requests.post(
       url,
       headers={"Authorization": f"Bearer {api_key}"},
       ...
   )
   rotator.record_usage(api_key)  # After successful request
   ```

3. Optionally show stats at the end:
   ```python
   # At end of eval script
   rotator.print_status()
   ```

That's it! The rotator handles all the complexity:
- Distributes load across all available keys
- Warns when approaching rate limits
- Waits automatically if all keys are at limit
- Thread-safe for parallel execution
    """)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sequential":
        example_sequential()
    elif len(sys.argv) > 1 and sys.argv[1] == "parallel":
        example_parallel()
    elif len(sys.argv) > 1 and sys.argv[1] == "pattern":
        example_integration_pattern()
    else:
        print("OpenRouter Key Rotation - Example Usage")
        print("=" * 60)
        print("\nAvailable examples:")
        print("  python3 scripts/openrouter-key-rotation-example.py sequential")
        print("  python3 scripts/openrouter-key-rotation-example.py parallel")
        print("  python3 scripts/openrouter-key-rotation-example.py pattern")
        print("\nFor testing without actual API calls:")
        print("  python3 scripts/openrouter-key-rotation.py --test 50")
        print("  python3 scripts/openrouter-key-rotation.py --status")
