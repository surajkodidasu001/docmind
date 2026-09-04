/**
 * Pure function: given an accumulated SSE text buffer, splits out complete
 * "data: {...}\n\n" events and returns the parsed JSON payloads plus
 * whatever incomplete trailing text should be carried over to the next
 * chunk. Extracted from api.js's queryStream so the buffering logic is
 * testable without a real fetch/ReadableStream.
 */
export function parseSSEBuffer(buffer) {
  const lines = buffer.split('\n\n')
  const remainder = lines.pop() ?? ''
  const events = []
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    events.push(JSON.parse(line.slice(6)))
  }
  return { events, remainder }
}
