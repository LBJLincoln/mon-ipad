'use client'

import { useState, useCallback, useEffect } from 'react'
import type { Source } from '@/types/chat'

interface UseSourceHighlightReturn {
  activeSourceIndex: number | null
  setActiveSourceIndex: (index: number | null) => void
  next: () => void
  prev: () => void
  totalSources: number
}

export function useSourceHighlight(sources: Source[]): UseSourceHighlightReturn {
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null)
  const total = sources.length

  const next = useCallback(() => {
    if (total === 0) return
    setActiveSourceIndex((prev) =>
      prev === null ? 0 : (prev + 1) % total
    )
  }, [total])

  const prev = useCallback(() => {
    if (total === 0) return
    setActiveSourceIndex((prev) =>
      prev === null ? total - 1 : (prev - 1 + total) % total
    )
  }, [total])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (!e.altKey || total === 0) return
      if (e.key === 'ArrowRight') {
        e.preventDefault()
        next()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        prev()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [next, prev, total])

  return {
    activeSourceIndex,
    setActiveSourceIndex,
    next,
    prev,
    totalSources: total,
  }
}
