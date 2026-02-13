'use client'

import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/landing/Hero'
import { BentoGrid } from '@/components/landing/BentoGrid'
import { HowItWorks } from '@/components/landing/HowItWorks'
import { TermiusModal } from '@/components/modal/TermiusModal'
import type { Sector } from '@/types/sector'

export default function Home() {
  const [activeSector, setActiveSector] = useState<Sector | null>(null)

  return (
    <>
      <Header />
      <main>
        <Hero />
        <BentoGrid onSelectSector={setActiveSector} />
        <HowItWorks />
      </main>
      <Footer />

      <TermiusModal
        sector={activeSector}
        onClose={() => setActiveSector(null)}
      />
    </>
  )
}
