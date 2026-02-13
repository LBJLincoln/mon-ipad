'use client'

import { ChevronLeft, ChevronRight } from 'lucide-react'

interface SourceNavigatorProps {
  current: number
  total: number
  onPrev: () => void
  onNext: () => void
  sectorColor: string
}

export function SourceNavigator({
  current,
  total,
  onPrev,
  onNext,
  sectorColor,
}: SourceNavigatorProps) {
  if (total === 0) return null

  return (
    <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.06]">
      <button
        onClick={onPrev}
        className="p-1 rounded-lg hover:bg-white/[0.06] transition-colors"
      >
        <ChevronLeft className="w-3.5 h-3.5 text-tx2" />
      </button>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-mono font-medium" style={{ color: sectorColor }}>
          {current + 1}
        </span>
        <span className="text-[11px] text-tx3">/</span>
        <span className="text-[11px] font-mono text-tx3">
          {total}
        </span>
        <span className="text-[11px] text-tx3 ml-1">sources</span>
      </div>
      <button
        onClick={onNext}
        className="p-1 rounded-lg hover:bg-white/[0.06] transition-colors"
      >
        <ChevronRight className="w-3.5 h-3.5 text-tx2" />
      </button>
    </div>
  )
}
