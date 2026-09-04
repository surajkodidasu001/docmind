import { useState } from 'react'
import CitationText from './CitationText'
import SourcesPanel from './SourcesPanel'

export default function ChatMessage({ message }) {
  const [expandTrace, setExpandTrace] = useState(false)
  const [highlighted, setHighlighted] = useState(null)

  if (message.role === 'user') {
    return <div className="message message--user">{message.text}</div>
  }

  const handleCitationClick = (indices) => {
    setHighlighted(indices)
    const el = document.getElementById(`source-${indices[0]}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    setTimeout(() => setHighlighted(null), 2000)
  }

  return (
    <div className="message message--assistant">
      <div className="message-body">
        <CitationText
          text={message.text}
          onCitationClick={handleCitationClick}
          flaggedSentences={message.flagged_claims}
        />
        {message.streaming && <span className="cursor-blink">▍</span>}
      </div>

      {!message.streaming && (
        <>
          <div className="message-meta">
            {message.confidence !== undefined && (
              <span className={`badge badge--confidence-${confidenceTier(message.confidence)}`}>
                {Math.round(message.confidence * 100)}% confidence
              </span>
            )}
            {message.from_cache && <span className="badge badge--cache">⚡ from cache</span>}
            {message.model_used && <span className="badge badge--model">{message.model_used}</span>}
            {message.trace?.total_cost_usd !== undefined && (
              <span className="badge badge--cost">${message.trace.total_cost_usd.toFixed(5)}</span>
            )}
          </div>

          <SourcesPanel
            sources={message.sources}
            highlighted={highlighted}
            contradictions={message.contradictions}
          />

          {message.trace && (
            <button className="trace-toggle" onClick={() => setExpandTrace((v) => !v)}>
              {expandTrace ? 'Hide' : 'Show'} pipeline trace
            </button>
          )}
          {expandTrace && (
            <pre className="trace-json">{JSON.stringify(message.trace, null, 2)}</pre>
          )}
        </>
      )}
    </div>
  )
}

function confidenceTier(c) {
  if (c >= 0.75) return 'high'
  if (c >= 0.5) return 'medium'
  return 'low'
}
