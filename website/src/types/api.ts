export interface ChatRequest {
  query: string
  sectorId: string
}

export interface PipelineInfo {
  name: string
  databases: string[]
  model?: string
}

export interface MetricsInfo {
  latency_ms?: number
  tokens_used?: number
  retrieval_ms?: number
  generation_ms?: number
}

export interface TraceStep {
  node: string
  status: 'success' | 'error' | 'skipped'
  duration_ms?: number
}

export interface ChatResponse {
  answer: string
  sources: ApiSource[]
  confidence?: number
  version?: string
  trace_id?: string
  sources_count?: number
  pipeline?: PipelineInfo
  metrics?: MetricsInfo
  trace?: TraceStep[]
}

export interface ApiSource {
  title: string
  content: string
  score?: number
  metadata?: Record<string, unknown>
}

export interface RawN8nResponse {
  response?: string
  answer?: string
  result?: string
  interpretation?: string
  final_response?: string
  output?: string
  sources?: ApiSource[]
  context?: ApiSource[]
  documents?: ApiSource[]
  confidence?: number
  score?: number
  version?: string
  trace_id?: string
  sources_count?: number
  _pipeline?: string
  _metrics?: Record<string, unknown>
  _trace?: Record<string, unknown>[]
  [key: string]: unknown
}
