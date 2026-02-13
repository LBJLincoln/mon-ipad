'use client'

import { motion } from 'framer-motion'
import { Search, Zap } from 'lucide-react'

export function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-12 overflow-hidden">
      {/* Mesh gradient background */}
      <div className="mesh-gradient absolute inset-0" />

      {/* Floating orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/5 w-[600px] h-[600px] bg-ac/[0.06] rounded-full blur-[150px] animate-pulse-slow" />
        <div className="absolute bottom-1/3 right-1/5 w-[500px] h-[500px] bg-pp/[0.04] rounded-full blur-[130px] animate-pulse-slow" style={{ animationDelay: '2s' }} />
        <div className="absolute top-2/3 left-1/2 w-[400px] h-[400px] bg-gn/[0.03] rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '4s' }} />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        {/* Status badge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass text-[13px] text-tx2 mb-8">
            <Zap className="w-3.5 h-3.5 text-yl" />
            <span>Intelligence documentaire multi-pipeline</span>
          </div>
        </motion.div>

        {/* Headline */}
        <motion.h1
          className="text-[56px] md:text-[80px] lg:text-[96px] font-bold tracking-[-0.04em] leading-[0.95] mb-6"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.4, 0, 0.2, 1] }}
        >
          <span className="text-tx">Posez.</span>
          <br />
          <span className="text-gradient">Obtenez.</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          className="text-lg md:text-xl text-tx2 max-w-xl mx-auto mb-14 leading-relaxed tracking-[-0.01em]"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.4, 0, 0.2, 1] }}
        >
          4 pipelines RAG orchestres intelligemment.
          <br />
          Vos documents, une seule interface.
        </motion.p>

        {/* Command bar preview */}
        <motion.a
          href="#sectors"
          className="group mx-auto max-w-2xl flex items-center gap-4 h-14 px-5 rounded-2xl glass-strong cursor-pointer transition-all duration-300 hover:border-white/[0.15] hover:shadow-lg hover:shadow-ac/[0.05]"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.35, ease: [0.4, 0, 0.2, 1] }}
        >
          <Search className="w-5 h-5 text-tx3 group-hover:text-tx2 transition-colors" />
          <span className="text-[15px] text-tx3 group-hover:text-tx2 transition-colors flex-1 text-left">
            Posez une question dans n&apos;importe quel secteur...
          </span>
          <div className="flex items-center gap-1.5">
            <kbd className="hidden sm:inline text-[11px] text-tx3 px-2 py-0.5 rounded-md bg-white/[0.06] border border-white/[0.08] font-mono">
              ⌘K
            </kbd>
          </div>
        </motion.a>

        {/* Scroll hint */}
        <motion.div
          className="mt-16 flex flex-col items-center gap-2 text-tx3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.8 }}
        >
          <span className="text-[11px] uppercase tracking-[0.1em]">Choisir un secteur</span>
          <div className="w-[1px] h-8 bg-gradient-to-b from-tx3/40 to-transparent" />
        </motion.div>
      </div>
    </section>
  )
}
