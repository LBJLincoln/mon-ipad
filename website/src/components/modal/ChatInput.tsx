'use client'

import { useState, useRef, useCallback, type KeyboardEvent } from 'react'
import { ArrowUp } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading: boolean
  sectorColor: string
  placeholder?: string
}

export function ChatInput({
  onSend,
  isLoading,
  sectorColor,
  placeholder = 'Posez votre question...',
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, isLoading, onSend])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
    }
  }

  const hasContent = value.trim().length > 0

  return (
    <div className="relative">
      <div className="rounded-2xl bg-white/[0.04] border border-white/[0.08] focus-within:border-white/[0.14] focus-within:bg-white/[0.05] transition-all duration-200">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder}
          rows={1}
          disabled={isLoading}
          className="w-full resize-none bg-transparent px-4 pt-3.5 pb-12 text-[14px] text-tx placeholder:text-tx3 focus:outline-none disabled:opacity-50 leading-relaxed"
          style={{ minHeight: '52px', maxHeight: '160px' }}
        />

        {/* Bottom bar inside input */}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-tx3 font-mono">
              Multi-RAG
            </span>
          </div>
          <button
            onClick={handleSend}
            disabled={!hasContent || isLoading}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 disabled:opacity-20"
            style={{
              backgroundColor: hasContent ? sectorColor : 'rgba(255,255,255,0.06)',
              color: hasContent ? '#fff' : 'var(--tx3)',
            }}
          >
            <ArrowUp className="w-4 h-4" strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  )
}
