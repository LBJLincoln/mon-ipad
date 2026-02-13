'use client'

import { useState } from 'react'
import { FileText, Layers, BarChart3 } from 'lucide-react'
import { SourceCard } from './SourceCard'
import { SourceNavigator } from './SourceNavigator'
import type { Source } from '@/types/chat'

interface RightSidebarProps {
  sources: Source[]
  activeIndex: number | null
  onSelect: (index: number) => void
  onNext: () => void
  onPrev: () => void
  sectorColor: string
}

type Tab = 'sources' | 'pipeline' | 'metrics'

export function RightSidebar({
  sources,
  activeIndex,
  onSelect,
  onNext,
  onPrev,
  sectorColor,
}: RightSidebarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('sources')

  if (sources.length === 0) return null

  const tabs: { id: Tab; label: string; icon: typeof FileText }[] = [
    { id: 'sources', label: 'Sources', icon: FileText },
    { id: 'pipeline', label: 'Pipeline', icon: Layers },
    { id: 'metrics', label: 'Metriques', icon: BarChart3 },
  ]

  return (
    <div className="w-[340px] border-l border-white/[0.06] flex flex-col h-full bg-white/[0.015] overflow-hidden">
      {/* Tab bar — claude.ai artifact style */}
      <div className="flex items-center gap-0.5 px-2 pt-2 pb-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium rounded-lg transition-all duration-150 ${
              activeTab === tab.id
                ? 'bg-white/[0.06] text-tx'
                : 'text-tx3 hover:text-tx2 hover:bg-white/[0.03]'
            }`}
          >
            <tab.icon className="w-3 h-3" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'sources' && (
        <>
          <SourceNavigator
            current={activeIndex ?? 0}
            total={sources.length}
            onPrev={onPrev}
            onNext={onNext}
            sectorColor={sectorColor}
          />
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
            {sources.map((source, idx) => (
              <SourceCard
                key={idx}
                source={source}
                index={idx}
                isActive={idx === activeIndex}
                sectorColor={sectorColor}
                onClick={() => onSelect(idx)}
              />
            ))}
          </div>
        </>
      )}

      {activeTab === 'pipeline' && (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-2">Pipeline utilise</div>
              <div className="text-[14px] font-medium text-tx">Orchestrator</div>
              <div className="text-[12px] text-tx2 mt-1">Selection automatique basee sur la requete</div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-2">Bases interrogees</div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {['Pinecone', 'Neo4j', 'Supabase'].map((db) => (
                  <span
                    key={db}
                    className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-white/[0.04] text-tx2 border border-white/[0.06]"
                  >
                    {db}
                  </span>
                ))}
              </div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-3">Flux d&apos;execution</div>
              <div className="space-y-2">
                {['Reception', 'Classification', 'Retrieval', 'Generation', 'Reponse'].map((step, i) => (
                  <div key={step} className="flex items-center gap-2.5">
                    <div
                      className="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-mono font-bold"
                      style={{ backgroundColor: `${sectorColor}15`, color: sectorColor }}
                    >
                      {i + 1}
                    </div>
                    <span className="text-[12px] text-tx2">{step}</span>
                    <div className="flex-1 h-[1px] bg-white/[0.04]" />
                    <span className="text-[10px] text-tx3 font-mono">OK</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-3">Performance</div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Sources', value: `${sources.length}`, color: sectorColor },
                  { label: 'Confiance', value: '—', color: 'var(--gn)' },
                  { label: 'Latence', value: '< 5s', color: 'var(--yl)' },
                  { label: 'Tokens', value: '—', color: 'var(--pp)' },
                ].map((m) => (
                  <div key={m.label} className="text-center p-2 rounded-lg bg-white/[0.02]">
                    <div className="text-[15px] font-semibold font-mono" style={{ color: m.color }}>
                      {m.value}
                    </div>
                    <div className="text-[10px] text-tx3 mt-0.5">{m.label}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4 rounded-xl border border-dashed border-white/[0.08] bg-white/[0.01]">
              <div className="text-[12px] text-tx3 text-center">
                Metriques detaillees disponibles apres integration n8n enrichie
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
