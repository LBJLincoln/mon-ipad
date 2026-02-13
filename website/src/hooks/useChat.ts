'use client'

import { useState, useCallback, useRef } from 'react'
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
  const abortRef = useRef(false)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessageContent = useChatStore((s) => s.updateMessageContent)
  const updateMessageFull = useChatStore((s) => s.updateMessageFull)

  const send = useCallback(
    async (query: string) => {
      setIsLoading(true)
      setError(null)
      abortRef.current = false

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: query,
        timestamp: Date.now(),
      }
      addMessage(sectorId, conversationId, userMsg)

      // Create placeholder assistant message for streaming
      const assistantId = crypto.randomUUID()
      const placeholderMsg: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }
      addMessage(sectorId, conversationId, placeholderMsg)

      try {
        const res = await sendMessage({ query, sectorId })

        if (abortRef.current) return

        const sources: Source[] = res.sources.map((s) => ({
          title: s.title,
          content: s.content,
          score: s.score,
          metadata: s.metadata,
        }))

        // Streaming simulation: word by word at 15ms/word
        const words = res.answer.split(/(\s+)/)
        let accumulated = ''

        for (let i = 0; i < words.length; i++) {
          if (abortRef.current) return
          accumulated += words[i]
          updateMessageContent(sectorId, conversationId, assistantId, accumulated)
          if (i < words.length - 1 && words[i].trim()) {
            await new Promise((r) => setTimeout(r, 15))
          }
        }

        // Finalize with all enriched data
        updateMessageFull(sectorId, conversationId, assistantId, {
          content: res.answer,
          sources: sources.length > 0 ? sources : undefined,
          confidence: res.confidence,
          version: res.version,
          trace_id: res.trace_id,
          sources_count: res.sources_count,
          pipeline: res.pipeline,
          metrics: res.metrics,
          trace: res.trace,
        })
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Erreur inconnue'
        setError(message)

        updateMessageFull(sectorId, conversationId, assistantId, {
          content: `Erreur : ${message}`,
        })
      } finally {
        setIsLoading(false)
      }
    },
    [sectorId, conversationId, addMessage, updateMessageContent, updateMessageFull]
  )

  return { send, isLoading, error }
}
