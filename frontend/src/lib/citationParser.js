const CITATION_PATTERN = /\[(\d+(?:,\s*\d+)*)\]/g

/**
 * Pure function: splits answer text into an array of
 * { type: 'text', value } | { type: 'citation', indices, raw } parts.
 * Extracted from CitationText.jsx so the parsing logic itself is testable
 * without rendering a component.
 */
export function parseCitations(text) {
  const result = []
  let lastIndex = 0
  let match
  const pattern = new RegExp(CITATION_PATTERN.source, 'g')

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      result.push({ type: 'text', value: text.slice(lastIndex, match.index) })
    }
    const indices = match[1].split(',').map((n) => parseInt(n.trim(), 10))
    result.push({ type: 'citation', indices, raw: match[0] })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    result.push({ type: 'text', value: text.slice(lastIndex) })
  }
  return result
}

/**
 * Given the parsed parts of an answer (see parseCitations) and a set of
 * flagged sentence strings, returns a parallel array of booleans — one per
 * part — marking which citation parts are "near" a flagged sentence (i.e.
 * immediately follow it). Non-citation parts are always false.
 *
 * Written as an immutable reduce (no reassigned loop variable) so it's a
 * pure function usable directly inside a component's render without
 * tripping purity lints — extracted here rather than inlined in
 * CitationText.jsx for the same reason parseCitations was: testable
 * without rendering a component.
 */
export function computeCitationFlags(parts, flaggedSet) {
  const { flags } = parts.reduce(
    (acc, part) => {
      if (part.type === 'text') {
        return { runningText: acc.runningText + part.value, flags: [...acc.flags, false] }
      }
      const flagged = isNearFlagged(acc.runningText, flaggedSet)
      return { runningText: acc.runningText + part.raw, flags: [...acc.flags, flagged] }
    },
    { runningText: '', flags: [] },
  )
  return flags
}

function isNearFlagged(precedingText, flaggedSet) {
  const trimmed = precedingText.trim()
  for (const flagged of flaggedSet) {
    if (trimmed.endsWith(flagged.replace(/\s*\[\d+(?:,\s*\d+)*\]\s*$/, '').trim())) {
      return true
    }
  }
  return false
}
