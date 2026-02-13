'use client'

import { Bot, Github } from 'lucide-react'

export function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 glass-strong">
      <div className="max-w-7xl mx-auto px-6 h-12 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-ac/30 to-ac/10 flex items-center justify-center">
            <Bot className="w-4 h-4 text-ac" />
          </div>
          <span className="font-medium text-tx text-[15px] tracking-tight">
            Multi-RAG
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-8 text-[13px] text-tx2">
          <a href="#sectors" className="hover:text-tx transition-colors duration-200">
            Secteurs
          </a>
          <a href="#how-it-works" className="hover:text-tx transition-colors duration-200">
            Fonctionnement
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-tx transition-colors duration-200 flex items-center gap-1.5"
          >
            <Github className="w-3.5 h-3.5" />
            GitHub
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gn/10 border border-gn/20">
            <div className="w-1.5 h-1.5 rounded-full bg-gn animate-pulse" />
            <span className="text-[11px] text-gn font-medium">Live</span>
          </div>
        </div>
      </div>
    </header>
  )
}
