# Deploying the Self-Hosted Reranker on HuggingFace Spaces

## Quick Deploy (5 minutes)

### 1. Create HF Space

Go to https://huggingface.co/new-space and create:
- **Space name**: `nomos-reranker-api`
- **SDK**: Gradio
- **Hardware**: cpu-basic (free)
- **Visibility**: Public (required for free tier)

### 2. Upload Files

Upload these files to the Space root:
- `app.py` (from this directory)
- `requirements.txt` (from this directory)

### 3. Wait for Build

The Space will auto-build and start. First request triggers model download (~34MB for default small model).

### 4. Test

```bash
# Health check
curl https://lbjlincoln-nomos-reranker-api.hf.space/health

# Rerank test
curl -X POST https://lbjlincoln-nomos-reranker-api.hf.space/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is GDP growth?",
    "documents": ["GDP grew 3%", "The weather is nice", "Economic growth was strong"],
    "top_n": 3
  }'
```

### 5. Update n8n Workflows

```bash
source .env.local
python3 reranker/update-reranker-endpoint.py --endpoint https://lbjlincoln-nomos-reranker-api.hf.space
python3 n8n/sync.py  # Push to n8n
```

## Environment Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `RERANKER_MODEL` | `small` | Default model: nano, small, medium, large |
| `PORT` | `7860` | Server port |

## Model Comparison

| Model | Size | Latency (25 docs) | NDCG@10 | Best For |
|-------|------|-------------------|---------|----------|
| nano  | 4MB  | ~50ms   | ~70     | Lowest latency |
| small | 34MB | ~200ms  | ~74     | Production (default) |
| medium| 110MB| ~500ms  | ~76     | Higher accuracy |
| large | 150MB| ~700ms  | ~78     | Best accuracy |

## API Format

### Jina/Cohere-compatible (what n8n uses)

```json
POST /v1/rerank
{
  "model": "jina-reranker-v2-base-multilingual",
  "query": "search query",
  "documents": ["doc1", "doc2", "doc3"],
  "top_n": 5
}

Response:
{
  "model": "ms-marco-MiniLM-L-12-v2",
  "results": [
    {"index": 1, "relevance_score": 0.95, "document": {"text": "doc2"}},
    {"index": 0, "relevance_score": 0.82, "document": {"text": "doc1"}},
    {"index": 2, "relevance_score": 0.45, "document": {"text": "doc3"}}
  ],
  "_self_hosted": true,
  "_cost": 0.0
}
```

### TEI-compatible

```json
POST /rerank
{
  "query": "search query",
  "texts": ["doc1", "doc2", "doc3"],
  "top_n": 5
}
```

## Adding to keepalive

Add to `scripts/keepalive-spaces.sh`:
```bash
curl -sf https://lbjlincoln-nomos-reranker-api.hf.space/health || echo "Reranker DOWN"
```
