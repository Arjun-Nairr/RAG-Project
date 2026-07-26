import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'
import BrandMark from './BrandMark'

const API_BASE = 'http://localhost:8000'

// Pacing for the answer reveal. These are *floors*, not added delays: a slow
// response is already past them and waits no longer. The point is that a very
// fast answer still reads as considered instead of snapping in.
const STAGE_SEARCHING_MS = 350
const REVEAL_FLOOR_MS = 700
const TICK_MS = 16
// Reveal speed is derived from elapsed time, not per-tick steps, so an
// irregular timer (background-tab throttling, a slow frame) still reveals the
// right amount instead of crawling. Rate scales with backlog so long answers
// never feel artificially throttled.
const CHARS_PER_SEC = 220
const BACKLOG_SCALE = 300

const SUGGESTED_PROMPTS = [
  'Summarize the key points',
  'What are the main contributions?',
  'Explain the core idea simply',
  'What are the limitations?',
]

const STAGE_LABELS = {
  searching: 'Searching your documents',
  reading: 'Reading sources',
}

function CopyIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function Sources({ sources }) {
  if (!sources?.length) return null
  return (
    <details className="sources">
      <summary>
        {sources.length} source{sources.length === 1 ? '' : 's'}
      </summary>
      <ul className="source-list">
        {sources.map((s, i) => (
          <li key={i} className="source-item">
            <div className="source-head">
              <span className="source-num">{i + 1}</span>
              <span className="source-name">{s.source}</span>
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
    <button
      className={`copy-btn ${copied ? 'copied' : ''}`}
      onClick={copy}
      title={copied ? 'Copied' : 'Copy answer'}
      aria-label={copied ? 'Copied' : 'Copy answer'}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </button>
  )
}

function AnswerBubble({ message }) {
  const { answer, sources, streaming, stage } = message
  const showStage = streaming && !answer && stage

  return (
    <div className="bubble bubble-a">
      {showStage ? (
        <span className="stage">
          <span className="stage-label">{STAGE_LABELS[stage]}</span>
          <span className="thinking-dots">
            <i></i>
            <i></i>
            <i></i>
          </span>
        </span>
      ) : (
        <div className="answer-text">
          <Markdown remarkPlugins={[remarkGfm]}>{answer}</Markdown>
          {streaming && <span className="stream-cursor" />}
        </div>
      )}
      {!streaming && <Sources sources={sources} />}
      {!streaming && answer && <CopyButton text={answer} />}
    </div>
  )
}

function Workspace({ studySet, onReset }) {
  const isUnreadable = studySet.text_quality === 'unreadable'
  const isLowQuality = studySet.text_quality === 'low'

  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState('')
  const [activeFile, setActiveFile] = useState(studySet.files[0] || null)
  const [dragging, setDragging] = useState(false)
  const threadRef = useRef(null)

  // reveal-pacing state (refs so the ticker isn't chasing React renders)
  const bufferRef = useRef('')
  const shownRef = useRef(0)
  const doneRef = useRef(false)
  const startRef = useRef(0)
  const lastTickRef = useRef(0)
  const tickerRef = useRef(null)
  const timeoutsRef = useRef([])

  const clearTimers = () => {
    if (tickerRef.current) {
      clearInterval(tickerRef.current)
      tickerRef.current = null
    }
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []
  }

  useEffect(() => clearTimers, [])

  const patchLast = (patch) =>
    setMessages((prev) => {
      if (prev.length === 0) return prev
      const copy = prev.slice()
      const last = copy[copy.length - 1]
      copy[copy.length - 1] = typeof patch === 'function' ? patch(last) : { ...last, ...patch }
      return copy
    })

  // load persisted history when the workspace opens (rendered as complete
  // answers - only live answers stream)
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

  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  /* Reveals buffered text at a steady pace so the answer flows out instead of
     popping in. Adaptive: a big backlog drains faster, so long answers never
     feel artificially throttled. */
  const startTicker = () => {
    if (tickerRef.current) return
    lastTickRef.current = Date.now()
    tickerRef.current = setInterval(() => {
      const now = Date.now()
      const dt = now - lastTickRef.current
      lastTickRef.current = now
      if (now - startRef.current < REVEAL_FLOOR_MS) return

      const pending = bufferRef.current
      if (shownRef.current >= pending.length) {
        if (doneRef.current) {
          clearTimers()
          patchLast((m) => ({ ...m, answer: pending, streaming: false, stage: null }))
        }
        return
      }

      const backlog = pending.length - shownRef.current
      const rate = CHARS_PER_SEC * (1 + backlog / BACKLOG_SCALE)
      shownRef.current = Math.min(pending.length, shownRef.current + (dt / 1000) * rate)
      const visible = pending.slice(0, Math.floor(shownRef.current))
      patchLast((m) => ({ ...m, answer: visible, stage: null }))
    }, TICK_MS)
  }

  const handleAsk = async (overrideQuestion) => {
    const q = (typeof overrideQuestion === 'string' ? overrideQuestion : question).trim()
    if (!q || asking) return

    setAsking(true)
    setAskError('')
    setQuestion('')

    clearTimers()
    bufferRef.current = ''
    shownRef.current = 0
    doneRef.current = false
    startRef.current = Date.now()

    setMessages((prev) => [
      ...prev,
      { question: q, answer: '', sources: [], streaming: true, stage: 'searching' },
    ])
    startTicker()

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
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.trim()) continue
          const evt = JSON.parse(line)
          if (evt.type === 'sources') {
            patchLast((m) => ({ ...m, sources: evt.sources }))
            // hold "searching" for its floor before switching stages
            const wait = Math.max(0, STAGE_SEARCHING_MS - (Date.now() - startRef.current))
            timeoutsRef.current.push(
              setTimeout(() => patchLast((m) => (m.answer ? m : { ...m, stage: 'reading' })), wait)
            )
          } else if (evt.type === 'delta') {
            bufferRef.current += evt.text
          } else if (evt.type === 'done') {
            doneRef.current = true
          }
        }
      }
      doneRef.current = true
    } catch (err) {
      clearTimers()
      setAskError(String(err.message || err))
      patchLast((m) => ({
        ...m,
        streaming: false,
        stage: null,
        answer: bufferRef.current || m.answer,
      }))
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
            <button className="btn-ghost" onClick={onReset}>
              + New
            </button>
          </header>

          {isLowQuality && (
            <div className="quality-banner quality-warn">
              This document's text looks unclear (common with scans or handwriting) —
              answers may vary.
            </div>
          )}

          {isUnreadable ? (
            <div className="thread">
              <div className="quality-banner quality-block">
                <strong>Couldn't read this document's text.</strong>
                <p>
                  This looks like a scanned image or handwriting with no readable text
                  layer, so there's nothing to search or answer from. You can still view
                  the file on the right — try re-uploading a typed or OCR'd version to ask
                  questions about it.
                </p>
              </div>
            </div>
          ) : (
            <>
          <div className="thread" ref={threadRef}>
            {messages.length === 0 && (
              <div className="thread-empty">
                <div className="thread-empty-icon" aria-hidden="true">
                  <BrandMark size={40} />
                </div>
                <p>
                  No questions yet.
                  <br />
                  Ask anything, or try one of these:
                </p>
                <div className="prompt-chips">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button key={p} className="chip" onClick={() => handleAsk(p)}>
                      {p}
                    </button>
                  ))}
                </div>
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
              <button className="btn" disabled={!question.trim() || asking} onClick={() => handleAsk()}>
                {asking ? '…' : 'Ask'}
              </button>
            </div>
          </div>
            </>
          )}
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
