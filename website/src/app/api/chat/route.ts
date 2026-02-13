import { NextRequest, NextResponse } from 'next/server'
import { parseN8nResponse } from '@/lib/parseResponse'

const N8N_HOST = process.env.N8N_HOST ?? 'http://34.136.180.66:5678'
const N8N_WEBHOOK_PATH =
  process.env.N8N_WEBHOOK_PATH ??
  '/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { query, sectorId } = body

    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'Le champ "query" est requis' },
        { status: 400 }
      )
    }

    const url = `${N8N_HOST}${N8N_WEBHOOK_PATH}`

    const n8nResponse = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, sector: sectorId }),
      signal: AbortSignal.timeout(120_000),
    })

    if (!n8nResponse.ok) {
      const errorText = await n8nResponse.text()
      console.error(`n8n error ${n8nResponse.status}:`, errorText)
      return NextResponse.json(
        { error: `Erreur backend: ${n8nResponse.status}` },
        { status: 502 }
      )
    }

    const rawData = await n8nResponse.json()
    const parsed = parseN8nResponse(rawData)

    return NextResponse.json(parsed)
  } catch (error) {
    console.error('Chat API error:', error)
    const message =
      error instanceof Error ? error.message : 'Erreur interne'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
