'use client'

import { Plus, MessageSquare } from 'lucide-react'
import type { Sector } from '@/types/sector'
import type { Conversation } from '@/types/chat'

interface LeftSidebarProps {
  sector: Sector
  conversations: Conversation[]
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onUseCaseClick: (question: string) => void
}

export function LeftSidebar({
  sector,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onUseCaseClick,
}: LeftSidebarProps) {
  return (
    <div className="w-56 border-r border-white/[0.06] flex flex-col h-full bg-white/[0.015]">
      {/* Header */}
      <div className="p-3 border-b border-white/[0.06]">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-[12px] font-medium transition-all duration-200 hover:brightness-110"
          style={{
            backgroundColor: `${sector.color}10`,
            color: sector.color,
          }}
        >
          <Plus className="w-3.5 h-3.5" />
          Nouvelle conversation
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto p-2">
        <div className="text-[10px] uppercase tracking-[0.08em] text-tx3 px-2 py-1.5 mb-1 font-medium">
          Historique
        </div>
        {conversations.length === 0 && (
          <p className="text-[11px] text-tx3 px-2 py-4 text-center">
            Aucune conversation
          </p>
        )}
        {[...conversations].reverse().map((conv) => {
          const preview =
            conv.messages[0]?.content.slice(0, 36) ?? 'Nouvelle conversation'
          return (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={`w-full text-left px-3 py-2 rounded-xl text-[12px] mb-0.5 transition-all duration-150 ${
                conv.id === activeConversationId
                  ? 'bg-white/[0.06] text-tx'
                  : 'text-tx2 hover:bg-white/[0.03]'
              }`}
            >
              <div className="flex items-center gap-2">
                <MessageSquare className="w-3 h-3 shrink-0 opacity-50" />
                <span className="truncate">{preview}</span>
              </div>
            </button>
          )
        })}
      </div>

      {/* Use Cases */}
      <div className="border-t border-white/[0.06] p-3">
        <div className="text-[10px] uppercase tracking-[0.08em] text-tx3 mb-2 font-medium">
          Cas d&apos;usage
        </div>
        <div className="flex flex-col gap-1">
          {sector.useCases.map((uc) => (
            <button
              key={uc.label}
              onClick={() => onUseCaseClick(uc.question)}
              className="text-left px-2.5 py-2 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] transition-all duration-150 group"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-tx2 group-hover:text-tx transition-colors">
                  {uc.label}
                </span>
                {uc.roi && (
                  <span
                    className="text-[9px] font-medium px-1.5 py-0.5 rounded-md"
                    style={{
                      backgroundColor: `${sector.color}10`,
                      color: sector.color,
                    }}
                  >
                    {uc.roi}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
