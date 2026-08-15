import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createSession,
  deleteSession,
  getMessages,
  listSessions,
  streamChat,
  type ChatMessage,
  type Session,
} from './lib/api'
import './App.css'

interface LocalMessage extends ChatMessage {
  streaming?: boolean
}

function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendUp, setBackendUp] = useState<boolean | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // --- backend health ---
  const checkBackend = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/health')
      setBackendUp(res.ok)
    } catch {
      setBackendUp(false)
    }
  }, [])

  useEffect(() => {
    checkBackend()
    const t = setInterval(checkBackend, 15000)
    return () => clearInterval(t)
  }, [checkBackend])

  // --- session list ---
  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listSessions())
    } catch (e) {
      setError(`Failed to load sessions: ${e}`)
    }
  }, [])

  useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  // --- load messages for a session ---
  const loadMessages = useCallback(async (id: string) => {
    setActiveId(id)
    setMessages([])
    setError(null)
    try {
      const msgs = await getMessages(id)
      setMessages(msgs)
    } catch (e) {
      setError(`Failed to load messages: ${e}`)
    }
  }, [])

  // --- new chat ---
  const newChat = async () => {
    try {
      const s = await createSession()
      await refreshSessions()
      setActiveId(s.id)
      setMessages([])
    } catch (e) {
      setError(`Failed to create session: ${e}`)
    }
  }

  // --- delete session ---
  const removeSession = async (id: string) => {
    try {
      await deleteSession(id)
      if (activeId === id) {
        setActiveId(null)
        setMessages([])
      }
      await refreshSessions()
    } catch (e) {
      setError(`Failed to delete session: ${e}`)
    }
  }

  // --- send + stream ---
  const send = async () => {
    const text = input.trim()
    if (!text || busy || !activeId) return
    setInput('')
    setBusy(true)
    setError(null)

    // optimistically append user message + placeholder assistant
    const userMsg: LocalMessage = {
      id: `local-${Date.now()}`,
      session_id: activeId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    const asstMsg: LocalMessage = {
      id: `local-asst-${Date.now()}`,
      session_id: activeId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      streaming: true,
    }
    setMessages((prev) => [...prev, userMsg, asstMsg])

    const abort = new AbortController()
    abortRef.current = abort

    let acc = ''
    try {
      await streamChat(
        activeId,
        text,
        (evt) => {
          if (evt.type === 'delta' && evt.content) {
            acc += evt.content
            setMessages((prev) =>
              prev.map((m) => (m.id === asstMsg.id ? { ...m, content: acc } : m)),
            )
          } else if (evt.type === 'tool') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstMsg.id
                  ? { ...m, content: m.content + `\n\n[🔧 ${evt.name}] ${evt.output}\n` }
                  : m,
              ),
            )
          } else if (evt.type === 'error') {
            setError(evt.message || 'chat error')
          }
        },
        abort.signal,
      )
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setError(`Chat failed: ${e}`)
      }
    } finally {
      abortRef.current = null
      setMessages((prev) =>
        prev.map((m) => (m.id === asstMsg.id ? { ...m, streaming: false } : m)),
      )
      setBusy(false)
      await refreshSessions()
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  // --- autoscroll ---
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-head">
          <span className="logo">◈</span>
          <h1>Vortex</h1>
        </div>
        <button className="new-chat" onClick={newChat}>
          + New Chat
        </button>
        <nav className="session-list">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`session-item ${s.id === activeId ? 'active' : ''}`}
              onClick={() => loadMessages(s.id)}
            >
              <span className="session-title">{s.title || 'New chat'}</span>
              <button
                className="session-del"
                onClick={(e) => {
                  e.stopPropagation()
                  removeSession(s.id)
                }}
                title="Delete"
              >
                ×
              </button>
            </div>
          ))}
          {sessions.length === 0 && <div className="empty">No chats yet</div>}
        </nav>
        <div className="sidebar-foot">
          <span className={`dot ${backendUp ? 'ok' : 'down'}`} />
          {backendUp === null ? 'checking…' : backendUp ? 'backend online' : 'backend offline'}
        </div>
      </aside>

      {/* Main chat pane */}
      <main className="chat">
        {!activeId ? (
          <div className="welcome">
            <h2>Vortex Agent</h2>
            <p>Autonomous local-first AI — with tools, memory, and a council.</p>
            <button className="new-chat" onClick={newChat}>
              Start a conversation
            </button>
          </div>
        ) : (
          <>
            <div className="messages" ref={scrollRef}>
              {messages.length === 0 && (
                <div className="empty-chat">Ask anything. I can run tools on the repo.</div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`msg ${m.role}`}>
                  <div className="msg-role">{m.role === 'user' ? 'You' : 'Vortex'}</div>
                  <div className="msg-content">
                    {m.content}
                    {m.streaming && <span className="caret">▍</span>}
                  </div>
                </div>
              ))}
            </div>
            {error && <div className="error-banner">{error}</div>}
            <div className="input-row">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                placeholder="Message Vortex… (Enter to send, Shift+Enter for newline)"
                rows={2}
              />
              {busy ? (
                <button className="send stop" onClick={stop}>
                  ■ Stop
                </button>
              ) : (
                <button className="send" onClick={send} disabled={!input.trim()}>
                  ➤
                </button>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
