import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

function Sources({ sources }) {
  if (!sources?.length) return null
  return (
    <details className="sources">
      <summary>{sources.length} source chunk(s)</summary>
      <ul className="source-list">
        {sources.map((s, i) => (
          <li key={i} className="source-item">
            <div className="source-head">
              <span className="source-name">{s.source}</span>
              {typeof s.distance === 'number' && (
                <span className="source-dist">distance {s.distance.toFixed(3)}</span>
              )}
            </div>
            <p className="source-snippet">{s.text}</p>
          </li>
        ))}
      </ul>
    </details>
  )
}

function Workspace({ studySet, onReset }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState('')
  const [activeFile, setActiveFile] = useState(studySet.files[0] || null)
  const threadRef = useRef(null)

  // load persisted history when the workspace opens
  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/study-sets/${studySet.id}/history`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return
        setMessages(
          (data.history || []).map((row) => ({
            question: row.question,
            answer: row.answer,
            sources: row.sources || [],
          }))
        )
      })
      .catch(() => {}) // history is best-effort; a failure just shows an empty thread
    return () => {
      cancelled = true
    }
  }, [studySet.id])

  // keep the thread pinned to the newest turn
  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, asking])

  const handleAsk = async () => {
    const q = question.trim()
    if (!q || asking) return
    setAsking(true)
    setAskError('')
    try {
      const res = await fetch(`${API_BASE}/study-sets/${studySet.id}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }
      const data = await res.json()
      setMessages((prev) => [...prev, { question: q, answer: data.answer, sources: data.sources }])
      setQuestion('')
    } catch (err) {
      setAskError(String(err.message || err))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="workspace">
      <section className="pane pane-chat">
        <header className="pane-head">
          <div>
            <h2 className="ws-title">{studySet.name}</h2>
            <p className="ws-sub">{studySet.files.length} document(s) · ask anything below</p>
          </div>
          <button className="btn-ghost" onClick={onReset}>+ New</button>
        </header>

        <div className="thread" ref={threadRef}>
          {messages.length === 0 && !asking && (
            <p className="thread-empty">
              No questions yet. Ask something about your documents to get started.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className="turn">
              <div className="bubble bubble-q">{m.question}</div>
              <div className="bubble bubble-a">
                <div className="answer-text">{m.answer}</div>
                <Sources sources={m.sources} />
              </div>
            </div>
          ))}
          {asking && (
            <div className="turn">
              <div className="bubble bubble-q">{question.trim()}</div>
              <div className="bubble bubble-a thinking">Thinking…</div>
            </div>
          )}
        </div>

        <div className="ask-bar">
          {askError && <p className="error-text">{askError}</p>}
          <div className="ask-row">
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
              {asking ? '…' : 'Ask'}
            </button>
          </div>
        </div>
      </section>

      <section className="pane pane-viewer">
        {studySet.files.length > 1 && (
          <div className="viewer-tabs">
            {studySet.files.map((f) => (
              <button
                key={f}
                className={`viewer-tab ${f === activeFile ? 'active' : ''}`}
                onClick={() => setActiveFile(f)}
                title={f}
              >
                {f}
              </button>
            ))}
          </div>
        )}
        {activeFile ? (
          <iframe
            className="pdf-frame"
            title={activeFile}
            src={`${API_BASE}/study-sets/${studySet.id}/files/${encodeURIComponent(activeFile)}`}
          />
        ) : (
          <div className="viewer-empty">No file to display</div>
        )}
      </section>
    </div>
  )
}

export default Workspace
