import type { RawN8nResponse, ChatResponse, ApiSource } from '@/types/api'

export function parseN8nResponse(raw: unknown): ChatResponse {
  const data = (Array.isArray(raw) ? raw[0] : raw) as RawN8nResponse

  const answer = extractAnswer(data)
  const sources = extractSources(data)
  const confidence = data.confidence ?? data.score ?? undefined

  return { answer, sources, confidence }
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
