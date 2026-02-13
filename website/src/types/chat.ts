import type { PipelineInfo, MetricsInfo, TraceStep } from './api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  confidence?: number
  timestamp: number
  version?: string
  trace_id?: string
  sources_count?: number
  pipeline?: PipelineInfo
  metrics?: MetricsInfo
  trace?: TraceStep[]
}

export interface Source {
  title: string
  content: string
  score?: number
  metadata?: Record<string, unknown>
}

export interface Conversation {
  id: string
  sectorId: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}
