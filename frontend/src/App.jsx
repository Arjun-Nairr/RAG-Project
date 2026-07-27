import { useCallback, useRef, useState } from 'react'
import './App.css'
import Workspace from './Workspace'
import BrandMark from './BrandMark'

const API_BASE = 'http://localhost:8000'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// no name typed - fall back to something derived from what was actually
// uploaded instead of a generic placeholder, since there's no study-set list
// where a custom name would help you find it again
function deriveDefaultName(fileList) {
  if (fileList.length === 0) return 'Untitled study set'
  const stripExt = (f) => f.name.replace(/\.pdf$/i, '')
  if (fileList.length === 1) return stripExt(fileList[0])
  return `${stripExt(fileList[0])} +${fileList.length - 1} more`
}

const DEMO_ICONS = { clear: '📄', semi_clear: '⚠️', unreadable: '🚫' }

function DemoPicker({ demos, loading, error, onPick, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box demo-picker" onClick={(e) => e.stopPropagation()}>
        <h3>Try a demo</h3>
        <p>No PDF handy? Jump straight into a pre-loaded example.</p>
        {loading && <p className="subtitle">Loading demos…</p>}
        {error && <p className="error-text">{error}</p>}
        {!loading && !error && (
          <div className="demo-cards">
            {demos.map((d) => (
              <button key={d.key} className="demo-card" onClick={() => onPick(d)}>
                <span className="demo-card-icon">{DEMO_ICONS[d.key] || '📄'}</span>
                <span className="demo-card-name">{d.name}</span>
                <span className="demo-card-desc">{d.description}</span>
              </button>
            ))}
          </div>
        )}
        <button className="btn-ghost demo-close" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function App() {
  const [files, setFiles] = useState([])
  const [name, setName] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | processing | done | error
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  const [showDemos, setShowDemos] = useState(false)
  const [demos, setDemos] = useState([])
  const [demosLoading, setDemosLoading] = useState(false)
  const [demosError, setDemosError] = useState('')

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
    formData.append('name', name.trim() || deriveDefaultName(files))
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

  const reset = () => {
    setFiles([])
    setName('')
    setResult(null)
    setStatus('idle')
  }

  const openDemos = async () => {
    setShowDemos(true)
    setDemosLoading(true)
    setDemosError('')
    try {
      const res = await fetch(`${API_BASE}/demo`)
      if (!res.ok) throw new Error('Demos are still warming up - try again in a moment.')
      const data = await res.json()
      setDemos(data.demos || [])
    } catch (err) {
      setDemosError(String(err.message || err))
    } finally {
      setDemosLoading(false)
    }
  }

  const pickDemo = (demo) => {
    // pre-seeded and already ready - jump straight into the workspace, no
    // upload or processing wait
    setResult(demo)
    setStatus('done')
    setShowDemos(false)
  }

  // once a study set is ready, hand off to the full-screen two-pane workspace
  if (status === 'done') {
    return <Workspace studySet={result} onReset={reset} />
  }

  return (
    <div className="page">
      {showDemos && (
        <DemoPicker
          demos={demos}
          loading={demosLoading}
          error={demosError}
          onPick={pickDemo}
          onClose={() => setShowDemos(false)}
        />
      )}
      <div className="card">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">Study Assistant</span>
        </div>
        <h1>New study set</h1>
        <p className="subtitle">Upload the PDFs you want to ask questions about.</p>
        {status !== 'processing' && (
          <button className="btn-ghost demo-trigger" onClick={openDemos}>
            ✨ Try a demo
          </button>
        )}

        {status === 'processing' ? (
          <div className="result">
            <div className="result-icon">
              <span className="thinking-dots">
                <i></i>
                <i></i>
                <i></i>
              </span>
            </div>
            <h2>{result.name}</h2>
            <p className="subtitle">
              Processing {result.files.length} file(s) — chunking, embedding, indexing...
            </p>
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
              {status === 'uploading'
                ? 'Uploading...'
                : `Upload ${files.length || ''} document${files.length === 1 ? '' : 's'}`}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default App
