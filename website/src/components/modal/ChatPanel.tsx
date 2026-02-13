'use client'

import { useRef, useEffect } from 'react'
import { ChatMessageBubble } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from '@/components/ui/TypingIndicator'
import { Bot } from 'lucide-react'
import type { ChatMessage } from '@/types/chat'

interface ChatPanelProps {
  messages: ChatMessage[]
  isLoading: boolean
  sectorColor: string
  sectorName: string
  onSend: (message: string) => void
  onSourceClick: (index: number) => void
}

export function ChatPanel({
  messages,
  isLoading,
  sectorColor,
  sectorName,
  onSend,
  onSourceClick,
}: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isLoading])

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      {/* Messages — centered like claude.ai */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
      >
        <div className="max-w-3xl mx-auto px-6 py-6 flex flex-col gap-5">
          {messages.length === 0 && (
            <div className="flex-1 flex items-center justify-center min-h-[50vh]">
              <div className="text-center max-w-sm">
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5"
                  style={{ backgroundColor: `${sectorColor}10` }}
                >
                  <Bot className="w-7 h-7" style={{ color: sectorColor }} />
                </div>
                <h3 className="text-[17px] font-semibold text-tx mb-2 tracking-[-0.01em]">
                  {sectorName}
                </h3>
                <p className="text-[13px] text-tx2 leading-relaxed">
                  Posez une question pour interroger la base documentaire.
                  Les reponses incluent les sources et scores de confiance.
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessageBubble
              key={msg.id}
              message={msg}
              sectorColor={sectorColor}
              onSourceClick={onSourceClick}
            />
          ))}

          {isLoading && <TypingIndicator color={sectorColor} />}
        </div>
      </div>

      {/* Input bar — bottom, claude.ai style */}
      <div className="border-t border-white/[0.06] bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a]/95 to-transparent">
        <div className="max-w-3xl mx-auto px-6 py-4">
          <ChatInput
            onSend={onSend}
            isLoading={isLoading}
            sectorColor={sectorColor}
          />
        </div>
      </div>
    </div>
  )
}
