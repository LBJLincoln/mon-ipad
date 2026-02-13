import type { Source } from '@/types/chat'

export interface HighlightSegment {
  text: string
  sourceIndex: number | null
}

/** Normalize text: strip diacritics for accent-insensitive matching */
function normalize(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

/**
 * Extracts phrases (3+ words) from source content,
 * then finds matches in the answer text with accent normalization.
 */
export function highlightAnswer(
  answer: string,
  sources: Source[]
): HighlightSegment[] {
  if (!sources.length) return [{ text: answer, sourceIndex: null }]

  const matches: { start: number; end: number; sourceIndex: number }[] = []
  const normalizedAnswer = normalize(answer)

  sources.forEach((source, sIdx) => {
    // Truncate source content to 500 chars for performance
    const content = source.content.slice(0, 500)
    const phrases = extractPhrases(content, 3)
    for (const phrase of phrases) {
      const normalizedPhrase = normalize(phrase)
      let pos = normalizedAnswer.indexOf(normalizedPhrase)
      while (pos !== -1) {
        matches.push({ start: pos, end: pos + phrase.length, sourceIndex: sIdx })
        pos = normalizedAnswer.indexOf(normalizedPhrase, pos + 1)
      }
    }
  })

  if (matches.length === 0) return [{ text: answer, sourceIndex: null }]

  // Sort by start, deduplicate overlapping
  matches.sort((a, b) => a.start - b.start)
  const merged = mergeOverlapping(matches)

  const segments: HighlightSegment[] = []
  let cursor = 0

  for (const m of merged) {
    if (m.start > cursor) {
      segments.push({ text: answer.slice(cursor, m.start), sourceIndex: null })
    }
    segments.push({
      text: answer.slice(m.start, m.end),
      sourceIndex: m.sourceIndex,
    })
    cursor = m.end
  }

  if (cursor < answer.length) {
    segments.push({ text: answer.slice(cursor), sourceIndex: null })
  }

  return segments
}

function extractPhrases(text: string, minWords: number): string[] {
  const sentences = text.split(/[.!?;\n]+/).filter((s) => s.trim().length > 0)
  const phrases: string[] = []
  const seen = new Set<string>()

  for (const sentence of sentences) {
    const words = sentence.trim().split(/\s+/)
    if (words.length >= minWords) {
      // Take sliding windows of minWords..maxWords (cap at 8)
      const maxLen = Math.min(words.length, 8)
      for (let len = minWords; len <= maxLen; len++) {
        for (let i = 0; i <= words.length - len; i++) {
          const phrase = words.slice(i, i + len).join(' ')
          const key = normalize(phrase)
          if (!seen.has(key)) {
            seen.add(key)
            phrases.push(phrase)
          }
        }
      }
    }
  }

  // Sort by length descending (prefer longer matches), cap at 30
  return phrases.sort((a, b) => b.length - a.length).slice(0, 30)
}

function mergeOverlapping(
  matches: { start: number; end: number; sourceIndex: number }[]
) {
  const result: typeof matches = []
  for (const m of matches) {
    const last = result[result.length - 1]
    if (last && m.start < last.end) {
      // Overlapping — extend if needed, keep first sourceIndex
      last.end = Math.max(last.end, m.end)
    } else {
      result.push({ ...m })
    }
  }
  return result
}
