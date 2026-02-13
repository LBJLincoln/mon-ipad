export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  confidence?: number
  timestamp: number
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
