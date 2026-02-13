'use client'

import { FileText } from 'lucide-react'
import type { Source } from '@/types/chat'

interface SourceCardProps {
  source: Source
  index: number
  isActive: boolean
  sectorColor: string
  onClick: () => void
}

export function SourceCard({
  source,
  index,
  isActive,
  sectorColor,
  onClick,
}: SourceCardProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3.5 rounded-xl transition-all duration-200 border ${
        isActive
          ? 'bg-white/[0.06] border-white/[0.12]'
          : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] hover:border-white/[0.08]'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Index badge */}
        <div
          className="w-6 h-6 shrink-0 rounded-lg flex items-center justify-center text-[10px] font-mono font-bold"
          style={{
            backgroundColor: isActive ? `${sectorColor}20` : `${sectorColor}10`,
            color: sectorColor,
          }}
        >
          {index + 1}
        </div>
        <div className="min-w-0 flex-1">
          {/* Title */}
          <div className="flex items-center gap-1.5 mb-1">
            <FileText className="w-3 h-3 text-tx3 shrink-0" />
            <span className="text-[12px] font-medium text-tx truncate">
              {source.title}
            </span>
          </div>
          {/* Content preview */}
          <p className="text-[11px] text-tx2 leading-relaxed line-clamp-3">
            {source.content}
          </p>
          {/* Score */}
          {source.score != null && (
            <div className="mt-2 flex items-center gap-2">
              <div
                className="h-1 rounded-full flex-1 bg-white/[0.06] overflow-hidden"
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.round(source.score * 100)}%`,
                    backgroundColor: sectorColor,
                    opacity: 0.6,
                  }}
                />
              </div>
              <span className="text-[10px] font-mono text-tx3">
                {(source.score * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </button>
  )
}
