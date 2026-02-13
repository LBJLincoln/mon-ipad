import type { RawN8nResponse, ChatResponse, ApiSource, PipelineInfo, MetricsInfo, TraceStep } from '@/types/api'

export function parseN8nResponse(raw: unknown): ChatResponse {
  const data = (Array.isArray(raw) ? raw[0] : raw) as RawN8nResponse

  const answer = extractAnswer(data)
  const sources = extractSources(data)
  const confidence = data.confidence ?? data.score ?? undefined

  // Enriched fields from n8n
  const version = typeof data.version === 'string' ? data.version : undefined
  const trace_id = typeof data.trace_id === 'string' ? data.trace_id : undefined
  const sources_count = typeof data.sources_count === 'number' ? data.sources_count : sources.length || undefined
  const pipeline = extractPipeline(data)
  const metrics = extractMetrics(data)
  const trace = extractTrace(data)

  return { answer, sources, confidence, version, trace_id, sources_count, pipeline, metrics, trace }
}

function extractAnswer(data: RawN8nResponse): string {
  const candidates = [
    data.response,
    data.answer,
    data.result,
    data.final_response,
    data.interpretation,
    data.output,
  ]

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }

  // Fallback: stringify the whole thing
  return JSON.stringify(data, null, 2)
}

function extractSources(data: RawN8nResponse): ApiSource[] {
  const candidates = [data.sources, data.context, data.documents]

  for (const candidate of candidates) {
    if (Array.isArray(candidate) && candidate.length > 0) {
      return candidate.map((s) => normalizeSource(s as unknown as Record<string, unknown>))
    }
  }

  return []
}

function normalizeSource(raw: Record<string, unknown>): ApiSource {
  return {
    title:
      (raw.title as string) ??
      (raw.name as string) ??
      (raw.source as string) ??
      'Source',
    content:
      (raw.content as string) ??
      (raw.text as string) ??
      (raw.pageContent as string) ??
      (raw.snippet as string) ??
      '',
    score: (raw.score as number) ?? (raw.similarity as number) ?? undefined,
    metadata: (raw.metadata as Record<string, unknown>) ?? undefined,
  }
}

function extractPipeline(data: RawN8nResponse): PipelineInfo | undefined {
  const name = data._pipeline as string | undefined
  if (!name) return undefined

  const dbMap: Record<string, string[]> = {
    standard: ['Pinecone'],
    graph: ['Neo4j', 'Supabase'],
    quantitative: ['Supabase'],
    orchestrator: ['Pinecone', 'Neo4j', 'Supabase'],
  }

  return {
    name,
    databases: dbMap[name.toLowerCase()] ?? ['Pinecone', 'Neo4j', 'Supabase'],
    model: typeof data._model === 'string' ? data._model : undefined,
  }
}

function extractMetrics(data: RawN8nResponse): MetricsInfo | undefined {
  const m = data._metrics
  if (!m || typeof m !== 'object') return undefined

  return {
    latency_ms: typeof m.latency_ms === 'number' ? m.latency_ms : undefined,
    tokens_used: typeof m.tokens_used === 'number' ? m.tokens_used : undefined,
    retrieval_ms: typeof m.retrieval_ms === 'number' ? m.retrieval_ms : undefined,
    generation_ms: typeof m.generation_ms === 'number' ? m.generation_ms : undefined,
  }
}

function extractTrace(data: RawN8nResponse): TraceStep[] | undefined {
  const t = data._trace
  if (!Array.isArray(t) || t.length === 0) return undefined

  return t.map((step) => ({
    node: typeof step.node === 'string' ? step.node : 'Unknown',
    status: (['success', 'error', 'skipped'].includes(step.status as string) ? step.status : 'success') as TraceStep['status'],
    duration_ms: typeof step.duration_ms === 'number' ? step.duration_ms : undefined,
  }))
}
