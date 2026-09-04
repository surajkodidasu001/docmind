import { describe, it, expect } from 'vitest'
import { parseCitations, computeCitationFlags } from '../citationParser'

describe('parseCitations', () => {
  it('returns plain text unchanged when there are no citations', () => {
    const parts = parseCitations('No citations here.')
    expect(parts).toEqual([{ type: 'text', value: 'No citations here.' }])
  })

  it('splits a single citation into text + citation parts', () => {
    const parts = parseCitations('The sky is blue [1].')
    expect(parts).toEqual([
      { type: 'text', value: 'The sky is blue ' },
      { type: 'citation', indices: [1], raw: '[1]' },
      { type: 'text', value: '.' },
    ])
  })

  it('parses multi-index citations like [2,3]', () => {
    const parts = parseCitations('Combined claim [2,3].')
    const citation = parts.find((p) => p.type === 'citation')
    expect(citation.indices).toEqual([2, 3])
  })

  it('handles multiple citations across a longer answer', () => {
    const text = 'First claim [1]. Second claim [2]. Third claim [1,3].'
    const parts = parseCitations(text)
    const citations = parts.filter((p) => p.type === 'citation')
    expect(citations).toHaveLength(3)
    expect(citations.map((c) => c.indices)).toEqual([[1], [2], [1, 3]])
  })

  it('does not treat non-citation bracket text as a citation', () => {
    const parts = parseCitations('Array syntax [x] is not a citation.')
    expect(parts.every((p) => p.type === 'text')).toBe(true)
  })

  it('is safe to call repeatedly on the same input (no shared regex state)', () => {
    const text = 'Claim [1] and claim [2].'
    const first = parseCitations(text)
    const second = parseCitations(text)
    expect(first).toEqual(second)
  })
})

describe('computeCitationFlags', () => {
  it('marks a citation as flagged when it directly follows a flagged sentence', () => {
    const text = 'This claim is unsupported. [1]'
    const parts = parseCitations(text)
    const flaggedSet = new Set(['This claim is unsupported.'])
    const flags = computeCitationFlags(parts, flaggedSet)
    const citationFlagIndex = parts.findIndex((p) => p.type === 'citation')
    expect(flags[citationFlagIndex]).toBe(true)
  })

  it('does not flag a citation whose sentence is not in the flagged set', () => {
    const text = 'This claim is fine. [1]'
    const parts = parseCitations(text)
    const flags = computeCitationFlags(parts, new Set(['Some other unsupported claim.']))
    const citationFlagIndex = parts.findIndex((p) => p.type === 'citation')
    expect(flags[citationFlagIndex]).toBe(false)
  })

  it('returns an all-false array when there are no flagged sentences', () => {
    const parts = parseCitations('First claim [1]. Second claim [2].')
    const flags = computeCitationFlags(parts, new Set())
    expect(flags.every((f) => f === false)).toBe(true)
  })

  it('flags only the specific citation adjacent to the flagged sentence, not all citations', () => {
    // Realistic format matches the backend's citation.py: the citation
    // marker sits right after the sentence-ending period, e.g.
    // "Good claim. [1] Bad claim. [2]" — not after a trailing period.
    const text = 'Good claim. [1] Bad claim. [2]'
    const parts = parseCitations(text)
    const flags = computeCitationFlags(parts, new Set(['Bad claim.']))
    const citationIndices = parts
      .map((p, i) => (p.type === 'citation' ? i : null))
      .filter((i) => i !== null)
    expect(flags[citationIndices[0]]).toBe(false) // "Good claim." citation
    expect(flags[citationIndices[1]]).toBe(true) // "Bad claim." citation
  })
})
