import { useState, useRef, useEffect, useCallback } from 'react'
import { queryStream, query as queryOnce, clearSession, cacheStats, listTables } from './api'
import UploadPanel from './components/UploadPanel'
import ChatMessage from './components/ChatMessage'
import './app.css'

function makeSessionId() {
  return Math.random().toString(36).slice(2, 10)
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streamMode, setStreamMode] = useState(true)
  const [busy, setBusy] = useState(false)
  const [lengthWarning, setLengthWarning] = useState('')
  const [sessionId] = useState(makeSessionId)
  const [cache, setCache] = useState(null)
  const [tables, setTables] = useState({})
  const abortRef = useRef(null)
  const scrollRef = useRef(null)

  const refreshIndexInfo = useCallback(async () => {
    try {
      const [c, t] = await Promise.all([cacheStats(), listTables()])
      setCache(c)
      setTables(t.tables)
    } catch {
      // backend not reachable yet — fine, sidebar just stays empty
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional
    // data-fetch-on-mount to sync sidebar stats with backend state; there's
    // no "derive during render" alternative for data that lives server-side
    refreshIndexInfo()
  }, [refreshIndexInfo])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const MAX_QUESTION_WORDS = 180

  const handleSend = async () => {
    const text = input.trim()
    if (!text || busy) return

    const wordCount = text.split(/\s+/).filter(Boolean).length
    if (wordCount > MAX_QUESTION_WORDS) {
      setLengthWarning(
        `Your question is ${wordCount} words — please shorten it to under ${MAX_QUESTION_WORDS} words for accurate results.`
      )
      return
    }
    setLengthWarning('')
    setInput('')
    setBusy(true)
    setMessages((prev) => [...prev, { role: 'user', text }])

    if (streamMode) {
      const assistantIndex = messages.length + 1
      setMessages((prev) => [...prev, { role: 'assistant', text: '', streaming: true }])

      const controller = new AbortController()
      abortRef.current = controller

      await queryStream(text, sessionId, {
        signal: controller.signal,
        onDelta: (delta) => {
          setMessages((prev) => {
            const next = [...prev]
            next[assistantIndex] = { ...next[assistantIndex], text: next[assistantIndex].text + delta }
            return next
          })
        },
        onFinal: (final) => {
          setMessages((prev) => {
            const next = [...prev]
            next[assistantIndex] = { ...next[assistantIndex], streaming: false, ...final }
            return next
          })
          setBusy(false)
          refreshIndexInfo()
        },
        onError: (err) => {
          setMessages((prev) => {
            const next = [...prev]
            next[assistantIndex] = {
              role: 'assistant',
              text: `Error: ${err.message}`,
              streaming: false,
              confidence: 0,
            }
            return next
          })
          setBusy(false)
        },
      })
    } else {
      try {
        const result = await queryOnce(text, sessionId)
        setMessages((prev) => [...prev, { role: 'assistant', streaming: false, ...result }])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: `Error: ${err.message}`, streaming: false, confidence: 0 },
        ])
      } finally {
        setBusy(false)
        refreshIndexInfo()
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClearConversation = async () => {
    await clearSession(sessionId)
    setMessages([])
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>🧠 DocMind</h1>
          <p className="tagline">Agentic document intelligence</p>
        </div>

        <UploadPanel onIndexChanged={refreshIndexInfo} />

        {Object.keys(tables).length > 0 && (
          <div className="tables-panel">
            <h4>Computable tables</h4>
            <ul>
              {Object.entries(tables).map(([name, cols]) => (
                <li key={name}>
                  <strong>{name}</strong>
                  <div className="table-columns">{cols.join(', ')}</div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="session-panel">
          <p className="session-id">Session: <code>{sessionId}</code></p>
          <button onClick={handleClearConversation}>Clear conversation</button>
        </div>

        {cache && (
          <p className="cache-line">
            Cache: {cache.entries} entries · {cache.total_hits} hits
          </p>
        )}

        <label className="stream-toggle">
          <input type="checkbox" checked={streamMode} onChange={(e) => setStreamMode(e.target.checked)} />
          Stream responses
        </label>
      </aside>

      <main className="chat-area">
        <div className="messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              Upload a document, then ask a question about it.
            </div>
          )}
          {messages.map((m, i) => (
            <ChatMessage key={i} message={m} />
          ))}
        </div>

        {lengthWarning && (<div className="length-warning">{lengthWarning}</div>)}
        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents…"
            rows={2}
          />
          <button onClick={handleSend} disabled={busy || !input.trim()}>
            {busy ? '…' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}
