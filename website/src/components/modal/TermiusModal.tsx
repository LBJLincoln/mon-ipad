'use client'

import { useEffect, useCallback, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Bot, PanelRightOpen, PanelRightClose } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useChat } from '@/hooks/useChat'
import { useSourceHighlight } from '@/hooks/useSourceHighlight'
import { LeftSidebar } from './LeftSidebar'
import { ChatPanel } from './ChatPanel'
import { RightSidebar } from './RightSidebar'
import type { Sector } from '@/types/sector'
import { useState } from 'react'

interface TermiusModalProps {
  sector: Sector | null
  onClose: () => void
}

export function TermiusModal({ sector, onClose }: TermiusModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const [artifactsOpen, setArtifactsOpen] = useState(true)

  const {
    getOrCreateConversation,
    getConversation,
    getConversations,
    activeConversationId,
    setActiveConversation,
    newConversation,
  } = useChatStore()

  const conversation = useMemo(() => {
    if (!sector) return null
    return getOrCreateConversation(sector.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sector?.id])

  const conversationId = activeConversationId ?? conversation?.id ?? ''

  const activeConv = sector
    ? getConversation(sector.id, conversationId)
    : null

  const messages = activeConv?.messages ?? []
  const conversations = sector ? getConversations(sector.id) : []

  const { send, isLoading } = useChat({
    sectorId: sector?.id ?? '',
    conversationId,
  })

  // Extract last assistant message with enriched data
  const lastAssistantMessage = useMemo(() => {
    return [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && (m.sources?.length || m.pipeline || m.content))
  }, [messages])

  const lastAssistantSources = lastAssistantMessage?.sources ?? []

  const {
    activeSourceIndex,
    setActiveSourceIndex,
    next: nextSource,
    prev: prevSource,
  } = useSourceHighlight(lastAssistantSources)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose()
    },
    [onClose]
  )

  const handleNewConversation = useCallback(() => {
    if (sector) newConversation(sector.id)
  }, [sector, newConversation])

  const handleUseCaseClick = useCallback(
    (question: string) => {
      send(question)
    },
    [send]
  )

  const handleSourceClick = useCallback(
    (index: number) => {
      setActiveSourceIndex(index)
      setArtifactsOpen(true)

      // Scroll-to-highlight: find the mark element in chat and flash it
      requestAnimationFrame(() => {
        const marks = modalRef.current?.querySelectorAll(`mark[data-source-index="${index}"]`)
        if (marks && marks.length > 0) {
          const mark = marks[0] as HTMLElement
          mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
          mark.classList.add('flash')
          setTimeout(() => mark.classList.remove('flash'), 800)
        }
      })
    },
    [setActiveSourceIndex]
  )

  const hasSources = lastAssistantSources.length > 0

  return (
    <AnimatePresence>
      {sector && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          onClick={handleBackdropClick}
        >
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          {/* Modal — Termius iPad style (2/3 center) */}
          <motion.div
            ref={modalRef}
            className="relative w-[92vw] max-w-[1400px] h-[88vh] rounded-2xl overflow-hidden border border-white/[0.08] shadow-2xl"
            style={{ background: '#0a0a0a' }}
            initial={{ opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Top bar — macOS style */}
            <div className="h-12 flex items-center justify-between px-4 border-b border-white/[0.06] bg-white/[0.02]">
              {/* Left: traffic lights + sector info */}
              <div className="flex items-center gap-3">
                {/* Traffic lights (decorative) */}
                <div className="hidden md:flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                  <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
                  <div className="w-3 h-3 rounded-full bg-[#28c840]" />
                </div>

                <div className="flex items-center gap-2.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${sector.color}15` }}
                  >
                    <Bot className="w-4 h-4" style={{ color: sector.color }} />
                  </div>
                  <div>
                    <span className="text-[13px] font-medium text-tx">{sector.name}</span>
                    <span className="text-[11px] text-tx3 ml-2">Multi-RAG</span>
                  </div>
                </div>
              </div>

              {/* Center: title (macOS style) */}
              <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gn/8 border border-gn/15">
                <div className="w-1.5 h-1.5 rounded-full bg-gn animate-pulse" />
                <span className="text-[10px] text-gn font-medium tracking-wide">CONNECTE</span>
              </div>

              {/* Right: actions */}
              <div className="flex items-center gap-1">
                {hasSources && (
                  <button
                    onClick={() => setArtifactsOpen(!artifactsOpen)}
                    className="p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors text-tx3 hover:text-tx2"
                    title={artifactsOpen ? 'Masquer artifacts' : 'Afficher artifacts'}
                  >
                    {artifactsOpen ? (
                      <PanelRightClose className="w-4 h-4" />
                    ) : (
                      <PanelRightOpen className="w-4 h-4" />
                    )}
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors text-tx3 hover:text-tx2"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* 3-panel layout */}
            <div className="flex h-[calc(100%-48px)]">
              {/* Left Sidebar */}
              <div className="hidden md:block">
                <LeftSidebar
                  sector={sector}
                  conversations={conversations}
                  activeConversationId={conversationId}
                  onSelectConversation={setActiveConversation}
                  onNewConversation={handleNewConversation}
                  onUseCaseClick={handleUseCaseClick}
                />
              </div>

              {/* Chat Panel — center, claude.ai style */}
              <ChatPanel
                messages={messages}
                isLoading={isLoading}
                sectorColor={sector.color}
                sectorName={sector.name}
                onSend={send}
                onSourceClick={handleSourceClick}
              />

              {/* Right Sidebar — Artifacts (claude.ai style) */}
              <AnimatePresence>
                {hasSources && artifactsOpen && (
                  <motion.div
                    className="hidden lg:block"
                    initial={{ width: 0, opacity: 0 }}
                    animate={{ width: 340, opacity: 1 }}
                    exit={{ width: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                  >
                    <RightSidebar
                      sources={lastAssistantSources}
                      activeIndex={activeSourceIndex}
                      onSelect={setActiveSourceIndex}
                      onNext={nextSource}
                      onPrev={prevSource}
                      sectorColor={sector.color}
                      pipeline={lastAssistantMessage?.pipeline}
                      metrics={lastAssistantMessage?.metrics}
                      trace={lastAssistantMessage?.trace}
                      confidence={lastAssistantMessage?.confidence}
                      version={lastAssistantMessage?.version}
                      sourcesCount={lastAssistantMessage?.sources_count}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
