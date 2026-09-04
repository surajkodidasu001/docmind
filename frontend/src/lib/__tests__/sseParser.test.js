import { describe, it, expect } from 'vitest'
import { parseSSEBuffer } from '../sseParser'

describe('parseSSEBuffer', () => {
  it('parses a single complete SSE event', () => {
    const buffer = 'data: {"type":"delta","text":"hello"}\n\n'
    const { events, remainder } = parseSSEBuffer(buffer)
    expect(events).toEqual([{ type: 'delta', text: 'hello' }])
    expect(remainder).toBe('')
  })

  it('parses multiple complete events in one buffer', () => {
    const buffer =
      'data: {"type":"delta","text":"a"}\n\n' +
      'data: {"type":"delta","text":"b"}\n\n' +
      'data: {"type":"final","confidence":0.9}\n\n'
    const { events, remainder } = parseSSEBuffer(buffer)
    expect(events).toHaveLength(3)
    expect(events[2]).toEqual({ type: 'final', confidence: 0.9 })
    expect(remainder).toBe('')
  })

  it('holds back an incomplete trailing event for the next chunk', () => {
    const buffer = 'data: {"type":"delta","text":"a"}\n\ndata: {"type":"delta","tex'
    const { events, remainder } = parseSSEBuffer(buffer)
    expect(events).toEqual([{ type: 'delta', text: 'a' }])
    expect(remainder).toBe('data: {"type":"delta","tex')
  })

  it('reassembles a split event correctly once the rest arrives', () => {
    const firstChunk = 'data: {"type":"delta","tex'
    const { events: e1, remainder: r1 } = parseSSEBuffer(firstChunk)
    expect(e1).toEqual([])

    const secondChunk = r1 + 't":"lo"}\n\n'
    const { events: e2, remainder: r2 } = parseSSEBuffer(secondChunk)
    expect(e2).toEqual([{ type: 'delta', text: 'lo' }])
    expect(r2).toBe('')
  })

  it('ignores non-data lines (SSE comments/keepalives)', () => {
    const buffer = ': keepalive\n\ndata: {"type":"delta","text":"x"}\n\n'
    const { events } = parseSSEBuffer(buffer)
    expect(events).toEqual([{ type: 'delta', text: 'x' }])
  })

  it('returns empty events and the whole buffer as remainder when nothing is complete yet', () => {
    const buffer = 'data: {"type":"delta"'
    const { events, remainder } = parseSSEBuffer(buffer)
    expect(events).toEqual([])
    expect(remainder).toBe(buffer)
  })
})
