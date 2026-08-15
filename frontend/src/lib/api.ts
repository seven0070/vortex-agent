// Vortex Agent API client — talks to the local backend at localhost:8000.
// Supports SSE streaming for chat deltas.

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

export interface Session {
  id: string
  title: string
  created_at: string | null
  updated_at: string | null
  message_count: number
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  created_at: string | null
}

export interface StreamEvent {
  type: 'delta' | 'tool' | 'done' | 'error'
  content?: string
  name?: string
  output?: string
  assistant?: string
  message?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export async function listSessions(): Promise<Session[]> {
  const data = await request<{ sessions: Session[] }>('/sessions')
  return data.sessions
}

export async function createSession(): Promise<Session> {
  return request<Session>('/sessions', { method: 'POST' })
}

export async function deleteSession(id: string): Promise<void> {
  await request(`/sessions/${id}`, { method: 'DELETE' })
}

export async function renameSession(id: string, title: string): Promise<Session> {
  return request<Session>(`/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function getMessages(id: string): Promise<ChatMessage[]> {
  const data = await request<{ messages: ChatMessage[] }>(`/sessions/${id}/messages`)
  return data.messages
}

/**
 * Stream a chat turn. onEvent is called per parsed SSE event.
 * Resolves when the stream ends (done or error).
 */
export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (evt: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`)
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('no response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE frames: "data: {...}\n\n"
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = frame.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (!payload) continue
      try {
        onEvent(JSON.parse(payload) as StreamEvent)
      } catch {
        // ignore malformed frames
      }
    }
  }
}
