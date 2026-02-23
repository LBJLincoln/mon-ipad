# Chatbot Knowledge Base Workflow

> Last updated: 2026-02-23T23:00:00+01:00

## Overview

This n8n workflow provides a simple chatbot endpoint powered by an embedded knowledge base extracted from:
- `docs/executive-summary.md` (project overview, metrics, architecture)
- `CLAUDE.md` (technical directives, infrastructure details)

The workflow receives user questions, searches the embedded knowledge for relevant context, and uses a free LLM (Llama 70B via OpenRouter) to generate helpful responses.

## Architecture

```
User Question (POST /webhook/chatbot-knowledge)
    ↓
Parse Input (sanitize, validate)
    ↓
Knowledge Search (keyword scoring, top 5 paragraphs)
    ↓
LLM Answer (Llama 70B with context)
    ↓
Format Response (JSON with answer, sources, metadata)
    ↓
Return to User
```

## Features

- **Embedded Knowledge**: No external database required. Knowledge is baked into the workflow.
- **Simple Search**: Keyword-based paragraph scoring for fast, relevant context retrieval.
- **Free LLM**: Uses `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter (no cost).
- **Error Handling**: Graceful error responses with proper HTTP status codes.
- **Sanitization**: Input sanitization (HTML removal, length limits, special char filtering).
- **Metadata**: Returns session ID, timestamp, model used, paragraphs found.

## Deployment

### 1. Import into n8n

**Via n8n UI:**
1. Open your n8n instance (HF Space or local)
2. Go to **Workflows** → **Import from File**
3. Select `chatbot-knowledge.json`
4. Click **Import**

**Via n8n CLI:**
```bash
# Copy the JSON to your n8n workflows directory
cp chatbot-knowledge.json /path/to/n8n/workflows/

# Or import via API
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @chatbot-knowledge.json
```

### 2. Configure Environment Variable

The workflow requires ONE environment variable:

```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**On HF Space:**
1. Go to your HF Space settings
2. Add a **Secret**: `OPENROUTER_API_KEY` = `your-key-here`
3. Restart the Space

**On VM/Codespace (docker-compose):**
Add to your `.env` file:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Activate the Workflow

1. Open the workflow in n8n UI
2. Click the **Activate** toggle (top-right)
3. Verify the webhook is active: you should see the webhook URL

## Usage

### Endpoint
```
POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge
```

### Request Format
```json
{
  "query": "What is Nomos AI?",
  "sessionId": "optional-session-id"
}
```

**Required fields:**
- `query` (string): The user's question. Max 500 characters after sanitization.

**Optional fields:**
- `sessionId` (string): For tracking conversations. Defaults to "anonymous".

### Response Format
```json
{
  "answer": "Nomos AI is a Multi-RAG Orchestrator — an AI system that answers complex questions...",
  "sources": [
    "Knowledge Base: executive-summary.md",
    "Knowledge Base: CLAUDE.md"
  ],
  "pipeline": "chatbot-knowledge",
  "sessionId": "optional-session-id",
  "timestamp": "2026-02-23T23:00:00.000Z",
  "paragraphsUsed": 5,
  "model": "meta-llama/llama-3.3-70b-instruct:free"
}
```

### Error Response
```json
{
  "error": true,
  "message": "Missing required field: query",
  "pipeline": "chatbot-knowledge",
  "timestamp": "2026-02-23T23:00:00.000Z"
}
```

## Testing

### Via curl
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the 4 RAG pipelines?",
    "sessionId": "test-123"
  }'
```

### Via Python
```python
import requests

response = requests.post(
    "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge",
    json={
        "query": "What is the current Phase 2 status?",
        "sessionId": "python-test"
    }
)

print(response.json())
```

### Via JavaScript
```javascript
fetch('https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'How many questions have been tested?',
    sessionId: 'js-test'
  })
})
  .then(res => res.json())
  .then(data => console.log(data));
```

## Updating the Knowledge Base

The knowledge is embedded directly in the **Knowledge Search** node (3rd node in the workflow).

### To update:
1. Open the workflow in n8n UI
2. Click the **Knowledge Search** node
3. Find the `KNOWLEDGE_BASE` constant (around line 5 in the code)
4. Replace or append new content
5. Save the node
6. Save the workflow

**Tips:**
- Keep paragraphs separated by double newlines (`\n\n`)
- Use markdown formatting (headers, lists, code blocks)
- Avoid very long paragraphs (break into smaller chunks for better search)
- Test after updates to verify relevance

### Automatic updates (future enhancement)
To sync automatically with `docs/executive-summary.md` and `CLAUDE.md`:
1. Add a **Cron Trigger** to the workflow (e.g., daily at 3 AM)
2. Add **Read Binary File** nodes to read the markdown files
3. Replace the `KNOWLEDGE_BASE` constant with `$node["Read File"].item.json.data`
4. Add error handling for file read failures

## Performance

- **Latency**: ~2-4 seconds per request (depends on OpenRouter load)
- **Concurrency**: Recommended max 3 concurrent requests (free LLM has rate limits)
- **Cost**: $0 (uses free OpenRouter models)
- **Knowledge size**: ~15KB embedded text (can scale to ~100KB before latency issues)

## Limitations

- **Static knowledge**: Must manually update the workflow to refresh knowledge
- **Simple search**: Keyword-based (no semantic similarity). For better search, replace with Pinecone/vector search.
- **No conversation memory**: Each request is stateless. For multi-turn conversations, add a memory node (store in Supabase or Redis).
- **Rate limits**: OpenRouter free tier has undocumented rate limits. Monitor for 429 errors.

## Troubleshooting

### Webhook returns 404
- Verify the workflow is **activated** in n8n UI
- Check the webhook path matches: `/webhook/chatbot-knowledge`
- Restart n8n if needed

### LLM returns empty/null response
- Check `OPENROUTER_API_KEY` is set correctly
- Verify the key is valid: test with `curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer $OPENROUTER_API_KEY"`
- Check OpenRouter status: https://status.openrouter.ai

### Knowledge search returns no paragraphs
- Verify the query contains meaningful words (>3 chars)
- Check the `KNOWLEDGE_BASE` constant has content
- Lower the keyword threshold (currently requires score > 0)

### Slow responses (>10s)
- OpenRouter free tier can be slow during peak hours
- Consider upgrading to a paid OpenRouter plan
- Or switch to a faster model (e.g., `google/gemma-2-27b-it:free`)

## Integration with Websites

### React/Next.js
```tsx
import { useState } from 'react';

export function Chatbot() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    const res = await fetch('https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, sessionId: 'website-user' })
    });
    const data = await res.json();
    setResponse(data);
    setLoading(false);
  };

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <button onClick={ask} disabled={loading}>
        {loading ? 'Thinking...' : 'Ask'}
      </button>
      {response && <div>{response.answer}</div>}
    </div>
  );
}
```

### Embed in rag-website, rag-pme-connectors, rag-pme-usecases
Replace broken chatbot endpoints with this new webhook:

**Before:**
```js
fetch('/api/chat', { ... }) // BROKEN
```

**After:**
```js
fetch('https://lbjlincoln-nomos-rag-engine.hf.space/webhook/chatbot-knowledge', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: userMessage })
})
```

## Maintenance

- **Update knowledge**: After significant project changes, update the `KNOWLEDGE_BASE` constant
- **Monitor usage**: Check n8n execution logs for errors or high latency
- **Rotate API keys**: If OpenRouter key leaks, rotate immediately and update the env var
- **Backup**: Export the workflow JSON regularly (via n8n UI or API)

## Future Enhancements

1. **Vector search**: Replace keyword search with Pinecone semantic search
2. **Conversation memory**: Store chat history in Redis or Supabase
3. **Multi-document**: Extend knowledge to include other project docs
4. **Auto-sync**: Cron job to reload knowledge from GitHub repo
5. **Analytics**: Track popular questions, response quality, latency
6. **Streaming**: Use OpenRouter streaming API for real-time responses

---

**Workflow Version**: v1.0
**Created**: 2026-02-23
**Repo**: `mon-ipad/n8n/chatbot/`
**Maintained by**: Claude Code (Opus 4.6)
