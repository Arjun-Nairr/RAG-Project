import { useCallback, useRef, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function App() {
  const [files, setFiles] = useState([])
  const [name, setName] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | done | error
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  // ask flow (only active once a study set is ready)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState(null)
  const [askError, setAskError] = useState('')

  const addFiles = useCallback((fileList) => {
    const pdfs = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name))
      const newOnes = pdfs.filter((f) => !existingNames.has(f.name))
      return [...prev, ...newOnes]
    })
  }, [])

  const removeFile = (fileName) => {
    setFiles((prev) => prev.filter((f) => f.name !== fileName))
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    addFiles(e.dataTransfer.files)
  }

  const pollStatus = (studySetId) => {
    const interval = setInterval(async () => {
      const res = await fetch(`${API_BASE}/study-sets/${studySetId}`)
      const data = await res.json()
      setResult(data)
      if (data.status === 'ready') {
        clearInterval(interval)
        setStatus('done')
      } else if (data.status === 'error') {
        clearInterval(interval)
        setStatus('error')
      }
    }, 1500)
  }

  const handleUpload = async () => {
    setStatus('uploading')
    const formData = new FormData()
    formData.append('name', name || 'Untitled study set')
    files.forEach((f) => formData.append('files', f))

    try {
      const res = await fetch(`${API_BASE}/study-sets`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setResult(data)
      setStatus('processing')
      pollStatus(data.id)
    } catch (err) {
      setResult({ error: String(err) })
      setStatus('error')
    }
  }

  const handleAsk = async () => {
    const q = question.trim()
    if (!q) return
    setAsking(true)
    setAskError('')
    setAnswer(null)
    try {
      const res = await fetch(`${API_BASE}/study-sets/${result.id}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }
      setAnswer(await res.json())
    } catch (err) {
      setAskError(String(err.message || err))
    } finally {
      setAsking(false)
    }
  }

  const reset = () => {
    setFiles([])
    setName('')
    setResult(null)
    setStatus('idle')
    setQuestion('')
    setAnswer(null)
    setAskError('')
  }

  return (
    <div className="page">
      <div className="card">
        <h1>New study set</h1>
        <p className="subtitle">Upload the PDFs you want to ask questions about.</p>

        {status === 'processing' ? (
          <div className="result">
            <div className="result-icon">…</div>
            <h2>{result.name}</h2>
            <p className="subtitle">Processing {result.files.length} file(s) — chunking, embedding, indexing...</p>
          </div>
        ) : status === 'done' ? (
          <div className="result">
            <div className="result-icon">✓</div>
            <h2>{result.name}</h2>
            <p className="subtitle">Ready — {result.files.length} file(s) indexed</p>

            <div className="ask-section">
              <textarea
                className="ask-input"
                placeholder="Ask a question about these documents..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAsk()
                  }
                }}
                rows={2}
              />
              <button className="btn" disabled={!question.trim() || asking} onClick={handleAsk}>
                {asking ? 'Thinking…' : 'Ask'}
              </button>

              {askError && <p className="error-text">{askError}</p>}

              {answer && (
                <div className="answer-block">
                  <div className="answer-text">{answer.answer}</div>
                  {answer.sources?.length > 0 && (
                    <details className="sources">
                      <summary>{answer.sources.length} source chunk(s) retrieved</summary>
                      <ul className="source-list">
                        {answer.sources.map((s, i) => (
                          <li key={i} className="source-item">
                            <div className="source-head">
                              <span className="source-name">{s.source}</span>
                              <span className="source-dist">distance {s.distance.toFixed(3)}</span>
                            </div>
                            <p className="source-snippet">{s.text}</p>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </div>

            <button className="btn btn-secondary" onClick={reset}>
              Upload another
            </button>
          </div>
        ) : (
          <>
            <input
              type="text"
              className="name-input"
              placeholder="Study set name (e.g. CS201 Midterm)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            <div
              className={`dropzone ${dragActive ? 'active' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                setDragActive(true)
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf"
                multiple
                hidden
                onChange={(e) => addFiles(e.target.files)}
              />
              <div className="dropzone-icon">+</div>
              <p>Drag PDFs here, or click to browse</p>
            </div>

            {files.length > 0 && (
              <ul className="file-list">
                {files.map((f) => (
                  <li key={f.name} className="file-row">
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{formatBytes(f.size)}</span>
                    <button
                      className="remove-btn"
                      onClick={() => removeFile(f.name)}
                      aria-label={`Remove ${f.name}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {status === 'error' && <p className="error-text">{result.error}</p>}

            <button
              className="btn"
              disabled={files.length === 0 || status === 'uploading'}
              onClick={handleUpload}
            >
              {status === 'uploading' ? 'Uploading...' : `Upload ${files.length || ''} document${files.length === 1 ? '' : 's'}`}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default App
