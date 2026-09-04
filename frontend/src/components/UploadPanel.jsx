import { useState, useRef } from 'react'
import { ingestFile, deleteDocument, resetIndex } from '../api'

export default function UploadPanel({ onIndexChanged }) {
  const [status, setStatus] = useState([])
  const [visionFallback, setVisionFallback] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState('')
  const fileInputRef = useRef(null)

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    for (const file of files) {
      try {
        const result = await ingestFile(file, visionFallback)
        setStatus((prev) => [
          { type: 'ok', text: `${file.name}: ${result.chunks_indexed} chunks indexed` },
          ...prev,
        ])
      } catch (err) {
        setStatus((prev) => [{ type: 'error', text: `${file.name}: ${err.message}` }, ...prev])
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
    onIndexChanged?.()
  }

  const handleDelete = async () => {
    if (!deleteTarget.trim()) return
    try {
      const result = await deleteDocument(deleteTarget.trim())
      setStatus((prev) => [
        { type: 'ok', text: `Deleted ${result.chunks_deleted} chunks from ${deleteTarget}` },
        ...prev,
      ])
      setDeleteTarget('')
      onIndexChanged?.()
    } catch (err) {
      setStatus((prev) => [{ type: 'error', text: err.message }, ...prev])
    }
  }

  const handleReset = async () => {
    await resetIndex()
    setStatus((prev) => [{ type: 'ok', text: 'Index and cache reset' }, ...prev])
    onIndexChanged?.()
  }

  return (
    <div className="upload-panel">
      <h3>Documents</h3>
      <label className="upload-dropzone">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleUpload}
          accept=".pdf,.docx,.pptx,.txt,.md,.csv,.html,.htm,.json"
        />
        <span>Click to upload — PDF, DOCX, PPTX, TXT, MD, CSV, HTML, JSON</span>
      </label>

      <label className="vision-toggle">
        <input
          type="checkbox"
          checked={visionFallback}
          onChange={(e) => setVisionFallback(e.target.checked)}
        />
        Use vision fallback for scanned PDF pages (costs one API call per image-only page)
      </label>

      <div className="delete-row">
        <input
          type="text"
          placeholder="filename to delete"
          value={deleteTarget}
          onChange={(e) => setDeleteTarget(e.target.value)}
        />
        <button onClick={handleDelete}>Delete</button>
      </div>

      <button className="reset-button" onClick={handleReset}>
        Reset entire index + cache
      </button>

      {status.length > 0 && (
        <ul className="status-log">
          {status.slice(0, 5).map((s, i) => (
            <li key={i} className={s.type === 'error' ? 'status-error' : 'status-ok'}>
              {s.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
