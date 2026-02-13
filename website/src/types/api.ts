export interface ChatRequest {
  query: string
  sectorId: string
}

export interface ChatResponse {
  answer: string
  sources: ApiSource[]
  confidence?: number
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
  [key: string]: unknown
}
