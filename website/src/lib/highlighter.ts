import type { Source } from '@/types/chat'

export interface HighlightSegment {
  text: string
  sourceIndex: number | null
}

/**
 * Extracts phrases (4+ words) from source content,
 * then finds fuzzy matches in the answer text.
 */
export function highlightAnswer(
  answer: string,
  sources: Source[]
): HighlightSegment[] {
  if (!sources.length) return [{ text: answer, sourceIndex: null }]

  const matches: { start: number; end: number; sourceIndex: number }[] = []

  sources.forEach((source, sIdx) => {
    const phrases = extractPhrases(source.content, 4)
    for (const phrase of phrases) {
      const lowerAnswer = answer.toLowerCase()
      const lowerPhrase = phrase.toLowerCase()
      let pos = lowerAnswer.indexOf(lowerPhrase)
      while (pos !== -1) {
        matches.push({ start: pos, end: pos + phrase.length, sourceIndex: sIdx })
        pos = lowerAnswer.indexOf(lowerPhrase, pos + 1)
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

  for (const sentence of sentences) {
    const words = sentence.trim().split(/\s+/)
    if (words.length >= minWords) {
      // Take sliding windows of minWords..maxWords
      const maxLen = Math.min(words.length, 12)
      for (let len = minWords; len <= maxLen; len++) {
        for (let i = 0; i <= words.length - len; i++) {
          phrases.push(words.slice(i, i + len).join(' '))
        }
      }
    }
  }

  // Deduplicate and sort by length descending (prefer longer matches)
  return [...new Set(phrases)].sort((a, b) => b.length - a.length).slice(0, 50)
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
