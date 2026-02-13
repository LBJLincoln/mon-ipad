'use client'

import { motion } from 'framer-motion'
import { MessageSquare, GitBranch, Database, CheckCircle } from 'lucide-react'

const steps = [
  {
    icon: MessageSquare,
    title: 'Question',
    description: 'En langage naturel, dans n\'importe quel secteur.',
    color: 'var(--ac)',
  },
  {
    icon: GitBranch,
    title: 'Orchestration',
    description: 'Selection automatique du meilleur pipeline RAG.',
    color: 'var(--pp)',
  },
  {
    icon: Database,
    title: 'Recherche',
    description: 'Pinecone, Neo4j et Supabase interroges simultanement.',
    color: 'var(--gn)',
  },
  {
    icon: CheckCircle,
    title: 'Reponse',
    description: 'Reponse sourcee avec scores de confiance.',
    color: 'var(--yl)',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="max-w-5xl mx-auto px-6 py-32">
      <motion.div
        className="text-center mb-16"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
      >
        <h2 className="text-[13px] uppercase tracking-[0.1em] text-tx3 mb-3">Processus</h2>
        <p className="text-[28px] md:text-[34px] font-bold tracking-[-0.03em] text-tx">
          De la question a la reponse.
        </p>
        <p className="text-[15px] text-tx2 mt-3">En moins de 5 secondes.</p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {steps.map((step, i) => (
          <motion.div
            key={step.title}
            className="relative p-6 rounded-2xl border border-white/[0.06] bg-white/[0.02] text-center"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            {/* Step number */}
            <div className="text-[11px] font-mono text-tx3 mb-4">
              {String(i + 1).padStart(2, '0')}
            </div>

            {/* Icon */}
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: `color-mix(in srgb, ${step.color} 12%, transparent)` }}
            >
              <step.icon className="w-5 h-5" style={{ color: step.color }} />
            </div>

            <h3 className="text-[15px] font-semibold text-tx mb-2 tracking-[-0.01em]">{step.title}</h3>
            <p className="text-[13px] text-tx2 leading-relaxed">
              {step.description}
            </p>

            {/* Connector line (not on last) */}
            {i < steps.length - 1 && (
              <div className="hidden lg:block absolute top-1/2 -right-2 w-4 h-[1px] bg-white/[0.08]" />
            )}
          </motion.div>
        ))}
      </div>
    </section>
  )
}
