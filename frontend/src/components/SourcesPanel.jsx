export default function SourcesPanel({ sources, highlighted, contradictions }) {
  if (!sources?.length) return null

  return (
    <div className="sources-panel">
      <h4>Sources</h4>
      <ol>
        {sources.map((s, i) => (
          <li
            key={i}
            id={`source-${i + 1}`}
            className={highlighted?.includes(i + 1) ? 'source-item source-item--highlighted' : 'source-item'}
          >
            <span className="source-index">[{i + 1}]</span> {s.source} — {s.location}
          </li>
        ))}
      </ol>

      {contradictions?.length > 0 && (
        <div className="contradictions">
          <h4>⚠️ Possible contradictions</h4>
          {contradictions.map((c, i) => (
            <p key={i} className="contradiction-item">
              <strong>{c.chunk_a.source}</strong> ({c.chunk_a.location}) vs{' '}
              <strong>{c.chunk_b.source}</strong> ({c.chunk_b.location}): {c.reason}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
