'use client'

import { useState } from 'react'
import { FileText, Layers, BarChart3, CheckCircle, XCircle, MinusCircle } from 'lucide-react'
import { SourceCard } from './SourceCard'
import { SourceNavigator } from './SourceNavigator'
import type { Source } from '@/types/chat'
import type { PipelineInfo, MetricsInfo, TraceStep } from '@/types/api'

interface RightSidebarProps {
  sources: Source[]
  activeIndex: number | null
  onSelect: (index: number) => void
  onNext: () => void
  onPrev: () => void
  sectorColor: string
  pipeline?: PipelineInfo
  metrics?: MetricsInfo
  trace?: TraceStep[]
  confidence?: number
  version?: string
  sourcesCount?: number
}

type Tab = 'sources' | 'pipeline' | 'metrics'

export function RightSidebar({
  sources,
  activeIndex,
  onSelect,
  onNext,
  onPrev,
  sectorColor,
  pipeline,
  metrics,
  trace,
  confidence,
  version,
  sourcesCount,
}: RightSidebarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('sources')

  if (sources.length === 0) return null

  const tabs: { id: Tab; label: string; icon: typeof FileText }[] = [
    { id: 'sources', label: 'Sources', icon: FileText },
    { id: 'pipeline', label: 'Pipeline', icon: Layers },
    { id: 'metrics', label: 'Metriques', icon: BarChart3 },
  ]

  const pipelineName = pipeline?.name ?? 'Orchestrator'
  const pipelineDbs = pipeline?.databases ?? ['Pinecone', 'Neo4j', 'Supabase']
  const modelName = pipeline?.model ?? 'arcee-ai/trinity-large-preview'
  const versionLabel = version ?? 'V8.0-CoT'

  const realSourcesCount = sourcesCount ?? sources.length
  const confidencePct = confidence != null ? Math.round(confidence * 100) : null
  const latencyMs = metrics?.latency_ms
  const tokensUsed = metrics?.tokens_used
  const retrievalMs = metrics?.retrieval_ms
  const generationMs = metrics?.generation_ms

  const traceSteps = trace ?? [
    { node: 'Reception', status: 'success' as const },
    { node: 'Classification', status: 'success' as const },
    { node: 'Retrieval', status: 'success' as const },
    { node: 'Generation', status: 'success' as const },
    { node: 'Reponse', status: 'success' as const },
  ]

  const statusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle className="w-3 h-3 text-gn" />
      case 'error': return <XCircle className="w-3 h-3 text-rd" />
      case 'skipped': return <MinusCircle className="w-3 h-3 text-tx3" />
      default: return <CheckCircle className="w-3 h-3 text-gn" />
    }
  }

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
              <div className="flex items-center gap-2">
                <div className="text-[14px] font-medium text-tx capitalize">{pipelineName}</div>
                <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold rounded bg-white/[0.06] text-tx2">
                  {versionLabel}
                </span>
              </div>
              <div className="text-[12px] text-tx2 mt-1">Selection automatique basee sur la requete</div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-2">Bases interrogees</div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {pipelineDbs.map((db) => (
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
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-2">Modele LLM</div>
              <div className="text-[12px] text-tx2 font-mono">{modelName}</div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-3">Trace d&apos;execution</div>
              <div className="space-y-2">
                {traceSteps.map((step, i) => (
                  <div key={step.node} className="flex items-center gap-2.5">
                    <div
                      className="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-mono font-bold"
                      style={{ backgroundColor: `${sectorColor}15`, color: sectorColor }}
                    >
                      {i + 1}
                    </div>
                    <span className="text-[12px] text-tx2">{step.node}</span>
                    <div className="flex-1 h-[1px] bg-white/[0.04]" />
                    {step.duration_ms != null ? (
                      <span className="text-[10px] text-tx3 font-mono">{step.duration_ms}ms</span>
                    ) : (
                      statusIcon(step.status)
                    )}
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
                <div className="text-center p-2 rounded-lg bg-white/[0.02]">
                  <div className="text-[15px] font-semibold font-mono" style={{ color: sectorColor }}>
                    {realSourcesCount}
                  </div>
                  <div className="text-[10px] text-tx3 mt-0.5">Sources</div>
                </div>
                <div className="text-center p-2 rounded-lg bg-white/[0.02]">
                  <div className="text-[15px] font-semibold font-mono" style={{ color: 'var(--gn)' }}>
                    {confidencePct != null ? `${confidencePct}%` : '\u2014'}
                  </div>
                  <div className="text-[10px] text-tx3 mt-0.5">Confiance</div>
                </div>
                <div className="text-center p-2 rounded-lg bg-white/[0.02]">
                  <div className="text-[15px] font-semibold font-mono" style={{ color: 'var(--yl)' }}>
                    {latencyMs != null ? `${(latencyMs / 1000).toFixed(1)}s` : '< 5s'}
                  </div>
                  <div className="text-[10px] text-tx3 mt-0.5">Latence</div>
                </div>
                <div className="text-center p-2 rounded-lg bg-white/[0.02]">
                  <div className="text-[15px] font-semibold font-mono" style={{ color: 'var(--pp)' }}>
                    {tokensUsed != null ? tokensUsed.toLocaleString() : '\u2014'}
                  </div>
                  <div className="text-[10px] text-tx3 mt-0.5">Tokens</div>
                </div>
              </div>
            </div>

            {/* Latency breakdown */}
            {(retrievalMs != null || generationMs != null) && (
              <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
                <div className="text-[11px] text-tx3 uppercase tracking-wide mb-3">Decomposition latence</div>
                <div className="space-y-2.5">
                  {retrievalMs != null && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-tx2">Retrieval</span>
                        <span className="text-[11px] text-tx3 font-mono">{retrievalMs}ms</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min((retrievalMs / (latencyMs ?? 5000)) * 100, 100)}%`,
                            backgroundColor: sectorColor,
                          }}
                        />
                      </div>
                    </div>
                  )}
                  {generationMs != null && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-tx2">Generation</span>
                        <span className="text-[11px] text-tx3 font-mono">{generationMs}ms</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min((generationMs / (latencyMs ?? 5000)) * 100, 100)}%`,
                            backgroundColor: 'var(--pp)',
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
              <div className="text-[11px] text-tx3 uppercase tracking-wide mb-2">Modele</div>
              <div className="text-[12px] text-tx2 font-mono">{modelName}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
