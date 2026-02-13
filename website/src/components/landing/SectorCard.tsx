'use client'

import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import type { Sector } from '@/types/sector'

interface SectorCardProps {
  sector: Sector
  index: number
  onSelect: (sector: Sector) => void
}

export function SectorCard({ sector, index, onSelect }: SectorCardProps) {
  const Icon = sector.icon

  return (
    <motion.button
      onClick={() => onSelect(sector)}
      className="group relative w-full text-left p-8 rounded-2xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-500 cursor-pointer overflow-hidden"
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{
        duration: 0.6,
        delay: 0.08 * index,
        ease: [0.4, 0, 0.2, 1],
      }}
      whileHover={{ y: -4 }}
    >
      {/* Glass card overlay */}
      <div className="absolute inset-0 glass opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl" />

      {/* Subtle glow on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-2xl"
        style={{
          background: `radial-gradient(800px circle at 50% 50%, ${sector.color}08, transparent 50%)`,
        }}
      />

      {/* Animated sector glow ring */}
      <div
        className="absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-700"
        style={{
          background: `linear-gradient(135deg, ${sector.color}20, transparent 40%, transparent 60%, ${sector.color}10)`,
        }}
      />

      {/* Top accent line */}
      <div
        className="absolute top-0 left-8 right-8 h-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{ background: `linear-gradient(90deg, transparent, ${sector.color}40, transparent)` }}
      />

      <div className="relative z-10">
        {/* Icon + Title */}
        <div className="flex items-start gap-4 mb-5">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${sector.color}12` }}
          >
            <Icon className="w-5 h-5" style={{ color: sector.color }} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-[17px] font-semibold text-tx mb-1 tracking-[-0.01em]">
              {sector.name}
            </h3>
            <p className="text-[13px] text-tx2 leading-relaxed">
              {sector.description}
            </p>
          </div>
        </div>

        {/* Use case chips — visible on hover */}
        <div className="flex flex-wrap gap-1.5 mb-4 h-0 group-hover:h-auto overflow-hidden opacity-0 group-hover:opacity-100 transition-all duration-300">
          {sector.useCases.slice(0, 3).map((uc) => (
            <span
              key={uc.label}
              className="px-2.5 py-1 text-[11px] font-medium rounded-full border"
              style={{
                backgroundColor: `${sector.color}08`,
                borderColor: `${sector.color}20`,
                color: sector.color,
              }}
            >
              {uc.label}
            </span>
          ))}
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/[0.06]">
          {sector.metrics.map((m) => (
            <div key={m.label}>
              <div
                className="text-[17px] font-semibold font-mono tabular-nums"
                style={{ color: sector.color }}
              >
                {m.value}
              </div>
              <div className="text-[11px] text-tx3 mt-0.5 leading-tight">{m.label}</div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="mt-6 flex items-center gap-2 text-[13px] font-medium" style={{ color: sector.color }}>
          <span>Interroger</span>
          <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1.5 transition-transform duration-300" />
        </div>
      </div>
    </motion.button>
  )
}
