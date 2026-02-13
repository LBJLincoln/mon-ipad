import { HardHat, Factory, TrendingUp, Scale } from 'lucide-react'
import type { Sector } from '@/types/sector'

export const SECTORS: Sector[] = [
  {
    id: 'btp',
    name: 'BTP & Construction',
    description:
      'Normes DTU, reglementations, CCTP et specifications techniques du batiment.',
    icon: HardHat,
    color: '#4C8BF5',
    colorVar: 'var(--ac)',
    gradient: 'from-blue-500/20 to-blue-600/5',
    metrics: [
      { label: 'Documents indexes', value: '2,400+' },
      { label: 'Precision', value: '92%' },
      { label: 'Temps de reponse', value: '<3s' },
    ],
    useCases: [
      {
        question: 'Quelles sont les normes DTU pour l\'isolation thermique des murs exterieurs ?',
        label: 'Normes DTU',
        roi: '-70% temps recherche',
      },
      {
        question: 'Quels sont les seuils reglementaires RE2020 pour un batiment tertiaire ?',
        label: 'RE2020',
        roi: 'Conformite garantie',
      },
      {
        question: 'Comment rediger un CCTP pour un lot plomberie ?',
        label: 'CCTP',
        roi: '-50% redaction',
      },
    ],
  },
  {
    id: 'industrie',
    name: 'Industrie',
    description:
      'Maintenance predictive, fiches techniques, procedures qualite et certifications ISO.',
    icon: Factory,
    color: '#30D982',
    colorVar: 'var(--gn)',
    gradient: 'from-green-500/20 to-green-600/5',
    metrics: [
      { label: 'Fiches techniques', value: '1,800+' },
      { label: 'Precision', value: '89%' },
      { label: 'Temps de reponse', value: '<4s' },
    ],
    useCases: [
      {
        question: 'Quelle est la procedure de maintenance preventive pour un compresseur Atlas Copco GA30+ ?',
        label: 'Maintenance',
        roi: '-40% arrets non planifies',
      },
      {
        question: 'Quelles sont les exigences ISO 9001:2015 pour la maitrise des documents ?',
        label: 'ISO 9001',
        roi: 'Audit-ready',
      },
      {
        question: 'Comment calibrer un capteur de pression differentielle ?',
        label: 'Calibration',
        roi: '-60% temps calibration',
      },
    ],
  },
  {
    id: 'finance',
    name: 'Finance',
    description:
      'Analyse financiere, reglementations bancaires, ratios et reporting IFRS.',
    icon: TrendingUp,
    color: '#F5B731',
    colorVar: 'var(--yl)',
    gradient: 'from-yellow-500/20 to-yellow-600/5',
    metrics: [
      { label: 'Rapports indexes', value: '3,200+' },
      { label: 'Precision', value: '94%' },
      { label: 'Temps de reponse', value: '<2s' },
    ],
    useCases: [
      {
        question: 'Quels sont les ratios prudentiels Bale III pour une banque de detail ?',
        label: 'Bale III',
        roi: 'Conformite regulatoire',
      },
      {
        question: 'Comment calculer le ratio de liquidite LCR selon les normes europeennes ?',
        label: 'LCR',
        roi: '-80% temps calcul',
      },
      {
        question: 'Quelles sont les nouvelles regles IFRS 17 pour les contrats d\'assurance ?',
        label: 'IFRS 17',
        roi: 'Mise en conformite',
      },
    ],
  },
  {
    id: 'juridique',
    name: 'Juridique',
    description:
      'Code civil, jurisprudence, contrats types et veille reglementaire.',
    icon: Scale,
    color: '#F08838',
    colorVar: 'var(--or)',
    gradient: 'from-orange-500/20 to-orange-600/5',
    metrics: [
      { label: 'Articles de loi', value: '5,000+' },
      { label: 'Precision', value: '91%' },
      { label: 'Temps de reponse', value: '<3s' },
    ],
    useCases: [
      {
        question: 'Quelles sont les obligations de l\'employeur en matiere de teletravail selon le Code du travail ?',
        label: 'Teletravail',
        roi: '-60% recherche juridique',
      },
      {
        question: 'Quels sont les delais de prescription en matiere contractuelle ?',
        label: 'Prescription',
        roi: 'Securite juridique',
      },
      {
        question: 'Comment rediger une clause de non-concurrence conforme a la jurisprudence ?',
        label: 'Non-concurrence',
        roi: '-50% revision contrats',
      },
    ],
  },
]
