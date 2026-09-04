import { useMemo } from 'react'
import { parseCitations, computeCitationFlags } from '../lib/citationParser'

/**
 * Renders answer text with [n] citation markers turned into clickable
 * superscript badges. Clicking one highlights + scrolls to the matching
 * entry in the sources list (via onCitationClick, passed an array of
 * 1-indexed source numbers).
 */
export default function CitationText({ text, onCitationClick, flaggedSentences = [] }) {
  const flaggedSet = useMemo(
    () => new Set(flaggedSentences.map((f) => f.sentence.trim())),
    [flaggedSentences],
  )

  const parts = useMemo(() => parseCitations(text), [text])
  const citationFlags = useMemo(() => computeCitationFlags(parts, flaggedSet), [parts, flaggedSet])

  return (
    <span className="citation-text">
      {parts.map((part, i) => {
        if (part.type === 'text') {
          return <span key={i}>{part.value}</span>
        }
        const flagged = citationFlags[i]
        return (
          <sup
            key={i}
            className={`citation-badge${flagged ? ' citation-badge--flagged' : ''}`}
            title={flagged ? 'This claim may not be well supported by its cited source' : `Source ${part.indices.join(', ')}`}
            onClick={() => onCitationClick?.(part.indices)}
          >
            {part.indices.map((n) => `[${n}]`).join('')}
          </sup>
        )
      })}
    </span>
  )
}
