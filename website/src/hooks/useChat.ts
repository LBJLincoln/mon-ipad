'use client'

import { useState, useCallback } from 'react'
import { sendMessage } from '@/lib/api'
import { useChatStore } from '@/stores/chatStore'
import type { ChatMessage, Source } from '@/types/chat'

interface UseChatOptions {
  sectorId: string
  conversationId: string
}

export function useChat({ sectorId, conversationId }: UseChatOptions) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const addMessage = useChatStore((s) => s.addMessage)

  const send = useCallback(
    async (query: string) => {
      setIsLoading(true)
      setError(null)

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: query,
        timestamp: Date.now(),
      }
      addMessage(sectorId, conversationId, userMsg)

      try {
        const res = await sendMessage({ query, sectorId })

        const sources: Source[] = res.sources.map((s) => ({
          title: s.title,
          content: s.content,
          score: s.score,
          metadata: s.metadata,
        }))

        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.answer,
          sources: sources.length > 0 ? sources : undefined,
          confidence: res.confidence,
          timestamp: Date.now(),
        }
        addMessage(sectorId, conversationId, assistantMsg)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Erreur inconnue'
        setError(message)

        const errorMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Erreur : ${message}`,
          timestamp: Date.now(),
        }
        addMessage(sectorId, conversationId, errorMsg)
      } finally {
        setIsLoading(false)
      }
    },
    [sectorId, conversationId, addMessage]
  )

  return { send, isLoading, error }
}
