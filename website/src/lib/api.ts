import type { ChatRequest, ChatResponse } from '@/types/api'

export async function sendMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Erreur ${res.status}: ${text}`)
  }

  return res.json()
}
