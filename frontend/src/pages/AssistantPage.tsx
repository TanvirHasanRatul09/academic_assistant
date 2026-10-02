import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, askAssistant, type AssistantResponse } from '../api'
import { AmbientBackground } from '../components/AmbientBackground'
import { Button, EmptyState, PageHeader, Spinner } from '../components/ui'
import { askOfflineAssistant, getCachedSessionUser } from '../offline'

type Turn = { id: string; role: 'user' | 'assistant'; content: string; response?: AssistantResponse }
const suggestions = [
  { label: 'Due soon', question: 'What assignments are due soon?' },
  { label: 'Today', question: 'What academic work do I have today?' },
  { label: 'Upcoming exams', question: 'Show my upcoming exams' },
  { label: 'This week', question: 'What is happening this week?' },
]
const MAX_TURNS = 12
const REQUEST_TIMEOUT_MS = 15_000

function errorStatus(caught: unknown): number | undefined {
  return caught instanceof ApiError ? caught.status : typeof caught === 'object' && caught !== null && 'status' in caught ? Number(caught.status) : undefined
}

function answerMode(response: AssistantResponse): string {
  if (response.mode === 'gemini') return 'AI-generated explanation · Gemini reachable'
  const status = response.gemini_status
  if (!status) return 'Deterministic offline fallback'
  if (status === 'not_configured') return 'Deterministic local answer · Gemini not configured'
  if (status === 'configured') return 'Deterministic local answer · Gemini not needed for this query'
  return `Deterministic local answer · Gemini unavailable (${status.replaceAll('_', ' ')})`
}

function assistantError(caught: unknown): string {
  if (errorStatus(caught) === 429) return 'The assistant rate limit was reached. Wait a moment, then retry.'
  if (caught instanceof Error && caught.message === 'assistant_timeout') return 'The assistant took longer than 15 seconds. Retry, or use a suggested local query.'
  return caught instanceof Error ? caught.message : 'The assistant is unavailable.'
}

async function withTimeout<T>(operation: Promise<T>): Promise<T> {
  let timer = 0
  try {
    return await Promise.race([
      operation,
      new Promise<never>((_, reject) => { timer = window.setTimeout(() => reject(new Error('assistant_timeout')), REQUEST_TIMEOUT_MS) }),
    ])
  } finally {
    window.clearTimeout(timer)
  }
}

export function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [error, setError] = useState('')
  const [lastQuestion, setLastQuestion] = useState('')
  const requestId = useRef(0)

  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => { requestId.current += 1; window.removeEventListener('online', handleOnline); window.removeEventListener('offline', handleOffline) }
  }, [])

  async function submit(question: string) {
    const trimmed = question.trim()
    if (trimmed.length < 2 || busy) return
    const prior = turns.slice(-6).map(({ role, content }) => ({ role, content: content.slice(0, 1000) }))
    const currentRequest = ++requestId.current
    setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'user' as const, content: trimmed }].slice(-MAX_TURNS))
    setLastQuestion(trimmed)
    setMessage('')
    setBusy(true)
    setError('')
    try {
      let response: AssistantResponse
      if (!navigator.onLine) {
        const user = await getCachedSessionUser()
        const offline = user ? await askOfflineAssistant(user.id, trimmed) : null
        if (!offline) throw new Error('No offline snapshot is available. Connect to the internet and synchronize Classroom first.')
        response = offline
      } else {
        try {
          response = await withTimeout(askAssistant(trimmed, prior))
        } catch (caught) {
          if (errorStatus(caught) !== 0) {
            if (currentRequest === requestId.current) setError(assistantError(caught))
            return
          }
          const user = await getCachedSessionUser()
          const offline = user ? await askOfflineAssistant(user.id, trimmed) : null
          if (!offline) throw new Error('The server is unavailable and this device has no synchronized snapshot.')
          response = offline
        }
      }
      if (currentRequest !== requestId.current) return
      setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant' as const, content: response.answer, response }].slice(-MAX_TURNS))
    } catch (caught) {
      if (currentRequest === requestId.current) setError(assistantError(caught))
    } finally {
      if (currentRequest === requestId.current) setBusy(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit(message)
  }

  function clearChat() {
    requestId.current += 1
    setTurns([])
    setMessage('')
    setError('')
    setLastQuestion('')
    setBusy(false)
  }

  return <section className="assistant-page" aria-labelledby="assistant-title">
    <PageHeader eyebrow="Your synchronized data" title="Academic assistant" description="Ask about tasks, deadlines, exams, and synchronized Classroom content." actions={turns.length > 0 ? <Button variant="secondary" onClick={clearChat}>Clear this chat</Button> : undefined} />
    <section className="assistant-trust-panel" aria-label="Assistant scope and privacy">
      <div><strong>{online ? 'Synchronized-data assistant' : 'Offline snapshot assistant'}</strong><p>{online ? 'Answers use only your selected courses and synchronized records. AI explanations may be imperfect—verify important details from the dashboard when needed.' : 'You are offline. Supported questions are answered deterministically from the last snapshot saved on this device.'}</p></div>
      <span className={online ? 'online' : 'offline'}>{online ? 'Online' : 'Offline'}</span>
    </section>

    {turns.length === 0 && <section className="assistant-welcome ambient-surface" aria-labelledby="assistant-start-title"><AmbientBackground variant="assistant" /><EmptyState title="Ask a focused academic question" description="I can find synchronized tasks, deadlines, exams, and matching course content. I cannot submit work, edit Classroom, or answer from data that has not been synchronized." /><div className="assistant-suggestions" aria-label="Suggested questions">{suggestions.map((item) => <Button variant="secondary" type="button" key={item.label} onClick={() => void submit(item.question)}>{item.label}</Button>)}</div></section>}

    <div className="assistant-thread" aria-live="polite" aria-busy={busy}>
      {turns.map((turn) => <article className={'assistant-turn ' + turn.role} key={turn.id}>
        <strong>{turn.role === 'user' ? 'You' : 'Assistant'}</strong>
        <p>{turn.content}</p>
        {turn.response && <div className="assistant-evidence">
          {turn.response.item && !["completion_status", "mark_as_completed", "mark_as_incomplete"].includes(turn.response.intent ?? "") && <section className="assistant-result-card" aria-label="Matched academic item">
            <strong>{turn.response.item.title} — {turn.response.item.course_name}</strong>
            <dl>
              <div><dt>Type</dt><dd>{turn.response.item.item_subtype.replaceAll('_', ' ')}</dd></div>
              {turn.response.item.completed !== null && <div><dt>Status</dt><dd>{turn.response.item.completed ? 'Completed' : 'Not completed'}</dd></div>}
              {(turn.response.item.due_at || turn.response.item.starts_at) && <div><dt>Date</dt><dd>{new Date(turn.response.item.due_at ?? turn.response.item.starts_at!).toLocaleString()}</dd></div>}
              <div><dt>Source</dt><dd>{turn.response.item.source_kind === 'manual' ? 'Added by you' : 'Google Classroom'}</dd></div>
            </dl>
          </section>}
          <p className="muted-copy"><strong>{answerMode(turn.response)}</strong> · Last successful sync: {turn.response.last_sync_at ? new Date(turn.response.last_sync_at).toLocaleString() : 'not available'}</p>
          {!turn.response.data_available && turn.response.answer_status !== 'ambiguous_course' && <p className="assistant-unavailable">No matching synchronized data was available. Synchronize Classroom and try again.</p>}
          {turn.response.sources.some((source) => (source.actions?.length ?? 0) > 0) && <div className="assistant-context-actions" aria-label="Relevant academic documents">
            {turn.response.sources.flatMap((source) => (source.actions ?? []).map((action) => <a key={`${source.source_url}-${action.url}`} href={action.url} target="_blank" rel="noreferrer">{action.label}</a>))}
          </div>}
        </div>}
      </article>)}
      {busy && <div className="assistant-loading" role="status"><Spinner /><span>{online ? 'Checking synchronized data and preparing an answer…' : 'Searching the saved offline snapshot…'}</span></div>}
    </div>

    {error && <div className="error-panel assistant-error" role="alert"><div><strong>Answer not available</strong><p>{error}</p></div>{lastQuestion && <Button variant="secondary" disabled={busy} onClick={() => void submit(lastQuestion)}>Retry</Button>}</div>}

    <form className="assistant-composer" onSubmit={onSubmit}>
      <label htmlFor="assistant-message">Ask a question</label>
      <div><input id="assistant-message" maxLength={500} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What assignments are due this week?" /><Button type="submit" loading={busy} disabled={busy || message.trim().length < 2}>Ask</Button></div>
      <small>{message.length}/500 · Enter sends the question.</small>
    </form>
    <p className="assistant-retention"><strong>Chat retention:</strong> This chat stays only in this page’s memory, keeps at most {MAX_TURNS} messages, and disappears when you clear it, refresh, sign out, or close the tab.</p>
  </section>
}






