'use client'

import { motion } from 'framer-motion'
import { SECTORS } from '@/lib/constants'
import { SectorCard } from './SectorCard'
import type { Sector } from '@/types/sector'

interface BentoGridProps {
  onSelectSector: (sector: Sector) => void
}

export function BentoGrid({ onSelectSector }: BentoGridProps) {
  return (
    <section id="sectors" className="max-w-5xl mx-auto px-6 pt-8 pb-16">
      <motion.div
        className="text-center mb-12"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
      >
        <h2 className="text-[13px] uppercase tracking-[0.1em] text-tx3 mb-3">Secteurs</h2>
        <p className="text-[28px] md:text-[34px] font-bold tracking-[-0.03em] text-tx">
          Choisissez votre domaine.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SECTORS.map((sector, i) => (
          <SectorCard
            key={sector.id}
            sector={sector}
            index={i}
            onSelect={onSelectSector}
          />
        ))}
      </div>
    </section>
  )
}
