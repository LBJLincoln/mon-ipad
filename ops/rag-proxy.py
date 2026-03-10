#!/usr/bin/env python3
"""Simple RAG proxy: E5 search + Groq LLM. Bypasses n8n complexity."""
import json, os, sys, requests
requests.packages.urllib3.disable_warnings()

PINECONE_KEY = os.environ.get('PINECONE_API_KEY', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')
E5_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"

def search_e5(question, sector=None, top_k=10):
    """Search E5 index with integrated embedding."""
    payload = {
        "query": {
            "top_k": top_k,
            "inputs": {"text": question},
            "filter": {"sector": {"$eq": sector}} if sector else {}
        },
        "fields": ["text", "sector", "source"]
    }
    r = requests.post(f"{E5_HOST}/records/namespaces/sectors/search",
        json=payload, headers={"Api-Key": PINECONE_KEY}, verify=False, timeout=30)
    if r.status_code != 200:
        return [], f"Pinecone error: {r.status_code}"
    hits = r.json().get("result", {}).get("hits", [])
    return hits, None

def generate_answer(question, context_docs, model="llama-3.3-70b-versatile"):
    """Generate answer using Groq."""
    context = "\n\n".join([
        f"[Source: {h.get('fields',{}).get('source','?')}] {h.get('fields',{}).get('text','')[:500]}"
        for h in context_docs[:5]
    ])
    
    prompt = f"""Tu es un expert sectoriel. Réponds à la question en te basant UNIQUEMENT sur les documents fournis.
Si les documents ne contiennent pas la réponse, dis-le clairement.
Cite les sources pertinentes.

DOCUMENTS:
{context}

QUESTION: {question}

RÉPONSE:"""

    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "temperature": 0.1},
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        timeout=30)
    if r.status_code != 200:
        return None, f"Groq error: {r.status_code} {r.text[:200]}"
    return r.json()["choices"][0]["message"]["content"], None

def rag_query(question, sector=None):
    """Full RAG pipeline: search + generate."""
    # Search
    hits, err = search_e5(question, sector)
    if err:
        return {"error": True, "message": err}
    if not hits:
        return {"error": False, "response": "Aucun document trouvé.", "sources": []}
    
    # Generate
    answer, err = generate_answer(question, hits)
    if err:
        return {"error": True, "message": err}
    
    sources = [{"id": h["_id"], "score": h["_score"], "sector": h.get("fields",{}).get("sector",""),
                "text": h.get("fields",{}).get("text","")[:200]} for h in hits[:5]]
    
    return {"error": False, "response": answer, "sources": sources, "n_hits": len(hits)}

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "Quels sont les marches publics BTP recents?"
    sector = sys.argv[2] if len(sys.argv) > 2 else None
    result = rag_query(question, sector)
    print(json.dumps(result, indent=2, ensure_ascii=False))
