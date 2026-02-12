import os
import json
from urllib import request, error

# --- Credentials ---
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = os.environ.get("PINECONE_HOST", "https://sota-rag-cohere-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io")

if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is required") 

COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")  # Set via environment variable
EMBEDDING_API_URL = "https://api.cohere.com/v2/embed"
EMBEDDING_MODEL = "embed-english-v3.0" # This is 1024-dim

def call_api(url, method, headers, data=None):
    body = json.dumps(data).encode() if data else None
    req = request.Request(url, data=body, method=method, headers=headers)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        body_content = e.read().decode() if e.fp else ""
        print(f"ERROR: API HTTP error {e.code} for {url}: {body_content}")
        raise
    except Exception as e:
        print(f"ERROR: API general error for {url}: {e}")
        raise

def get_embedding(text):
    print(f"Generating embedding for: '{text}' using {EMBEDDING_MODEL}...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {COHERE_API_KEY}"
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "texts": [text],
        "input_type": "search_query",
        "embedding_types": ["float"]
    }
    response = call_api(EMBEDDING_API_URL, "POST", headers, payload)
    embeddings = response["embeddings"]["float"][0]
    print(f"Generated embedding of dimension: {len(embeddings)}")
    return embeddings

def query_pinecone(vector):
    print(f"Querying Pinecone at {PINECONE_HOST} with {len(vector)}-dimensional vector...")
    headers = {
        "Content-Type": "application/json",
        "Api-Key": PINECONE_API_KEY
    }
    payload = {
        "vector": vector,
        "topK": 5,
        "includeMetadata": True
    }
    response = call_api(f"{PINECONE_HOST}/query", "POST", headers, payload)
    return response

if __name__ == "__main__":
    test_query = "What is the capital of Japan?"
    try:
        embedding = get_embedding(test_query)
        pinecone_response = query_pinecone(embedding)
        
        print("\n--- Pinecone Query Response ---")
        print(json.dumps(pinecone_response, indent=2))
        
        if pinecone_response.get("matches"):
            print("\nFound matches:")
            for match in pinecone_response["matches"]:
                print(f"  ID: {match['id']}, Score: {match['score']}, Content: {match['metadata'].get('content', 'N/A')[:100]}...")
        else:
            print("\nNo matches found.")

    except Exception as e:
        print(f"\nAn error occurred during verification: {e}")
