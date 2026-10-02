import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createPersonalTask, getPersonalTasks } from '../api'
import { PersonalTasksPanel } from './PersonalTasksPanel'

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, getPersonalTasks: vi.fn(), createPersonalTask: vi.fn(), updatePersonalTask: vi.fn(), deletePersonalTask: vi.fn() }
})

describe('personal academic tasks', () => {
  beforeEach(() => {
    vi.mocked(getPersonalTasks).mockResolvedValue([])
    vi.mocked(createPersonalTask).mockResolvedValue({ id: 'task-1', user_id: 'user-1', course_id: null, course_name: null, title: 'Physical assignment', details: null, event_type: 'assignment', starts_at: null, due_at: null, priority: 1, section: null, lab_group: null, completed: false, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), source_kind: 'manual' })
  })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('creates a task announced outside Classroom', async () => {
    render(<PersonalTasksPanel courses={[{ id: 'course-1', name: 'OS Theory' }]} />)
    await screen.findByText(/No personal tasks yet/)
    fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Physical assignment' } })
    fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'course-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save task' }))
    await waitFor(() => expect(createPersonalTask).toHaveBeenCalledWith(expect.objectContaining({ title: 'Physical assignment', course_id: 'course-1' })))
  })

  it('blocks a due date earlier than the start date', async () => {
    render(<PersonalTasksPanel courses={[]} />)
    await screen.findByText(/No personal tasks yet/)
    fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'AI quiz' } })
    fireEvent.change(screen.getByLabelText('Starts'), { target: { value: '2026-10-01T16:18' } })
    fireEvent.change(screen.getByLabelText('Due'), { target: { value: '2026-06-16T18:20' } })
    fireEvent.submit(screen.getByLabelText('Due').closest('form')!)

    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot be earlier/)
    expect(screen.getByLabelText('Due')).toHaveAttribute('aria-invalid', 'true')
    expect(createPersonalTask).not.toHaveBeenCalled()
  })
})
