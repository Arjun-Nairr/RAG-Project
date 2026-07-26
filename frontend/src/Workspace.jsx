import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'
import BrandMark from './BrandMark'

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

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked - ignore */
    }
  }
  return (
    <button className="copy-btn" onClick={copy} title="Copy answer">
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

function AnswerBubble({ message }) {
  const { answer, sources, streaming } = message
  return (
    <div className="bubble bubble-a">
      {answer ? (
        <div className="answer-text">
          <Markdown remarkPlugins={[remarkGfm]}>{answer}</Markdown>
          {streaming && <span className="stream-cursor" />}
        </div>
      ) : (
        <span className="thinking-dots">
          <i></i><i></i><i></i>
        </span>
      )}
      <Sources sources={sources} />
      {!streaming && answer && <CopyButton text={answer} />}
    </div>
  )
}

function Workspace({ studySet, onReset }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState('')
  const [activeFile, setActiveFile] = useState(studySet.files[0] || null)
  const [dragging, setDragging] = useState(false)
  const threadRef = useRef(null)

  // patch the most recent message immutably (used while streaming)
  const patchLast = (patch) =>
    setMessages((prev) => {
      if (prev.length === 0) return prev
      const copy = prev.slice()
      const last = copy[copy.length - 1]
      copy[copy.length - 1] = typeof patch === 'function' ? patch(last) : { ...last, ...patch }
      return copy
    })

  // load persisted history when the workspace opens (these render as full,
  // non-streaming answers)
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
            streaming: false,
          }))
        )
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [studySet.id])

  // keep the thread pinned to the newest turn as it grows
  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, asking])

  const handleAsk = async () => {
    const q = question.trim()
    if (!q || asking) return
    setAsking(true)
    setAskError('')
    setQuestion('')
    // placeholder we fill as the stream arrives
    setMessages((prev) => [...prev, { question: q, answer: '', sources: [], streaming: true }])

    try {
      const res = await fetch(`${API_BASE}/study-sets/${studySet.id}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok || !res.body) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep the trailing partial line
        for (const line of lines) {
          if (!line.trim()) continue
          const evt = JSON.parse(line)
          if (evt.type === 'sources') {
            patchLast((m) => ({ ...m, sources: evt.sources }))
          } else if (evt.type === 'delta') {
            patchLast((m) => ({ ...m, answer: m.answer + evt.text }))
          } else if (evt.type === 'done') {
            patchLast((m) => ({ ...m, streaming: false }))
          }
        }
      }
      patchLast((m) => ({ ...m, streaming: false }))
    } catch (err) {
      setAskError(String(err.message || err))
      patchLast((m) => ({ ...m, streaming: false, answer: m.answer || '_(failed to answer)_' }))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className={`workspace ${dragging ? 'dragging' : ''}`}>
      <PanelGroup direction="horizontal" autoSaveId="rag-workspace-split">
        <Panel className="pane pane-chat" defaultSize={42} minSize={26} maxSize={68} order={1}>
        <header className="pane-head">
          <div className="pane-head-left">
            <BrandMark size={30} />
            <div>
              <h2 className="ws-title">{studySet.name}</h2>
              <p className="ws-sub">{studySet.files.length} document(s) · ask anything below</p>
            </div>
          </div>
          <button className="btn-ghost" onClick={onReset}>+ New</button>
        </header>

        <div className="thread" ref={threadRef}>
          {messages.length === 0 && (
            <div className="thread-empty">
              <div className="thread-empty-icon" aria-hidden="true">
                <BrandMark size={40} />
              </div>
              <p>No questions yet.<br />Ask something about your documents to get started.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="turn">
              <div className="bubble bubble-q">{m.question}</div>
              <AnswerBubble message={m} />
            </div>
          ))}
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
        </Panel>

        <PanelResizeHandle className="resize-handle" onDragging={setDragging} />

        <Panel className="pane pane-viewer" minSize={32} order={2}>
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
        </Panel>
      </PanelGroup>
    </div>
  )
}

export default Workspace
