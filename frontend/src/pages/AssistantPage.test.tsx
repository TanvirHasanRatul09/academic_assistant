import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { askAssistant } from '../api'
import { AssistantPage } from './AssistantPage'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, askAssistant: vi.fn() }
})
vi.mock('../offline', () => ({ askOfflineAssistant: vi.fn(), getCachedSessionUser: vi.fn() }))

const response = {
  answer: '<img src=x onerror=alert(1)> Two assignments are due.',
  mode: 'gemini' as const,
  tool: 'get_upcoming_deadlines' as const,
  sources: [{ title: 'Lab report', course_name: 'Physics', source_url: 'https://classroom.google.com/c/1', event_type: 'assignment', due_at: '2026-09-28T12:00:00Z', actions: [{ label: 'Open marks PDF', url: 'https://drive.google.com/marks.pdf', kind: 'pdf' as const }] }],
  last_sync_at: '2026-09-27T12:00:00Z',
  data_available: true,
  answer_status: 'exact_match' as const,
  intent: 'marks_or_result',
  item: { title: 'Lab report', course_name: 'Physics', item_subtype: 'assignment', completed: false, due_at: '2026-09-28T12:00:00Z', source_kind: 'classroom' as const, source_url: 'https://classroom.google.com/c/1' },
  possible_matches: [],
}

describe('F8 assistant experience', () => {
  beforeEach(() => vi.mocked(askAssistant).mockResolvedValue(response))
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('labels AI answers, exposes contextual marks documents, and renders output as text', async () => {
    render(<AssistantPage />)
    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Show my marks PDF' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText(/Two assignments are due/)).toBeInTheDocument()
    expect(screen.getByText(/AI-generated explanation/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open marks PDF' })).toHaveAttribute('href', 'https://drive.google.com/marks.pdf')
    expect(screen.getByRole('region', { name: 'Matched academic item' })).toHaveTextContent('Not completed')
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect(screen.getByText(/Chat retention:/)).toBeInTheDocument()
  })


  it('clears page-session chat history visibly', async () => {
    render(<AssistantPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Today' }))
    await screen.findByText(/Two assignments are due/)
    fireEvent.click(screen.getByRole('button', { name: 'Clear this chat' }))
    await waitFor(() => expect(screen.queryByText(/Two assignments are due/)).not.toBeInTheDocument())
    expect(screen.getByText('Ask a focused academic question')).toBeInTheDocument()
  })

  it('does not show a synchronization failure beneath a course clarification', async () => {
    vi.mocked(askAssistant).mockResolvedValueOnce({
      ...response,
      answer: 'Which course do you mean: CSE 3208 or CSE 3214?',
      answer_status: 'ambiguous_course',
      data_available: false,
      item: null,
      sources: [],
    })
    render(<AssistantPage />)
    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Is the lab final complete?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText(/Which course do you mean/)).toBeInTheDocument()
    expect(screen.queryByText(/No matching synchronized data/)).not.toBeInTheDocument()
  })
})




