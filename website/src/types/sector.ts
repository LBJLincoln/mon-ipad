import type { LucideIcon } from 'lucide-react'

export interface Sector {
  id: string
  name: string
  description: string
  icon: LucideIcon
  color: string
  colorVar: string
  gradient: string
  metrics: {
    label: string
    value: string
  }[]
  useCases: UseCase[]
}

export interface UseCase {
  question: string
  label: string
  roi?: string
}
