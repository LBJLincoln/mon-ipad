'use client'

import { Bot, User } from 'lucide-react'
import { highlightAnswer, type HighlightSegment } from '@/lib/highlighter'
import type { ChatMessage as ChatMessageType } from '@/types/chat'

interface ChatMessageProps {
  message: ChatMessageType
  sectorColor: string
  onSourceClick?: (index: number) => void
}

export function ChatMessageBubble({
  message,
  sectorColor,
  onSourceClick,
}: ChatMessageProps) {
  const isUser = message.role === 'user'

  const segments: HighlightSegment[] =
    !isUser && message.sources?.length
      ? highlightAnswer(message.content, message.sources)
      : [{ text: message.content, sourceIndex: null }]

  return (
    <div className={`flex gap-3.5 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className="w-8 h-8 shrink-0 rounded-xl flex items-center justify-center mt-0.5"
        style={{
          backgroundColor: isUser ? 'rgba(255,255,255,0.06)' : `${sectorColor}12`,
        }}
      >
        {isUser ? (
          <User className="w-4 h-4 text-tx2" />
        ) : (
          <Bot className="w-4 h-4" style={{ color: sectorColor }} />
        )}
      </div>

      <div className={`max-w-[85%] min-w-0 ${isUser ? 'text-right' : ''}`}>
        {/* Role label */}
        <div className={`text-[11px] text-tx3 mb-1.5 font-medium ${isUser ? 'text-right' : ''}`}>
          {isUser ? 'Vous' : 'Assistant'}
        </div>

        {/* Message body */}
        <div
          className={`inline-block text-[14px] leading-[1.6] ${
            isUser
              ? 'px-4 py-3 rounded-2xl rounded-tr-md bg-white/[0.06] text-tx'
              : 'text-tx/90'
          }`}
        >
          {segments.map((seg, i) =>
            seg.sourceIndex !== null ? (
              <mark
                key={i}
                className="bg-transparent cursor-pointer hover:opacity-80 transition-opacity"
                style={{
                  borderBottom: `2px solid ${sectorColor}50`,
                  color: 'inherit',
                  textDecoration: 'none',
                }}
                onClick={() => onSourceClick?.(seg.sourceIndex!)}
              >
                {seg.text}
              </mark>
            ) : (
              <span key={i}>{seg.text}</span>
            )
          )}
        </div>

        {/* Source badges */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {message.sources.map((src, idx) => (
              <button
                key={idx}
                onClick={() => onSourceClick?.(idx)}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-md transition-all hover:scale-105"
                style={{
                  backgroundColor: `${sectorColor}12`,
                  color: sectorColor,
                  border: `1px solid ${sectorColor}20`,
                }}
              >
                <span className="font-mono">[{idx + 1}]</span>
                <span className="max-w-[120px] truncate">{src.title}</span>
              </button>
            ))}
            {message.confidence != null && (
              <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-mono font-medium rounded-md bg-white/[0.04] text-tx3 border border-white/[0.06]">
                {Math.round(message.confidence * 100)}%
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
